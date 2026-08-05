"""The masthead hosts the Profile-run bar on its version rail by absolute
geometry, not a layout — so a centre widget that grows silently gets positioned
off the rail and clipped. That happened when the bar gained its second line
("Location being edited", #130): the rail was a fixed 28 px, the bar became
40 px, and the centring maths put it 6 px ABOVE the rail with its bottom cut off
by the masthead's own edge. These tests pin the invariant that matters — the
centre widget is fully inside both the rail and the masthead."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings, QSize                # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from core.file_manager import FileManager, Project       # noqa: E402
from core.measurement_target import RUN_TYPE_PROFILING   # noqa: E402
from core.settings import AppSettings                    # noqa: E402
from ui.masthead_header import MastheadHeader            # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,       # noqa: E402
                                       MeasurementTargetController)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Tall(QWidget):
    """A centre widget taller than the default rail."""
    def __init__(self, h: int):
        super().__init__()
        self._h = h
        QLabel("x", self)

    def sizeHint(self) -> QSize:            # noqa: N802
        return QSize(300, self._h)


def _assert_center_fits(mast: MastheadHeader) -> None:
    w = mast._center_widget
    g = w.geometry()
    rail_top = mast.height() - mast._rail_h
    assert g.top() >= rail_top, (
        f"centre widget starts {rail_top - g.top()} px above the rail")
    assert g.bottom() <= mast.height(), (
        f"centre widget overflows the masthead by {g.bottom() - mast.height()} px")


def test_default_height_is_unchanged_for_a_short_widget(qapp):
    mast = MastheadHeader(version="9.9.9")
    mast.resize(1000, mast.sizeHint().height())
    mast.set_center_widget(_Tall(22))
    assert mast.height() == 116                  # the long-standing masthead height
    _assert_center_fits(mast)


@pytest.mark.parametrize("h", [30, 40, 56, 80])
def test_rail_grows_so_a_taller_widget_still_fits(qapp, h):
    mast = MastheadHeader(version="9.9.9")
    mast.resize(1000, mast.sizeHint().height())
    mast.set_center_widget(_Tall(h))
    mast.resize(1000, mast.sizeHint().height())
    assert mast.height() > 116
    _assert_center_fits(mast)


def test_the_real_target_bar_fits_on_the_rail(qapp, tmp_path):
    """The case that actually broke: the two-line Profile-run bar."""
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # rail/bar geometry pivots on real text widths
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir()
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    Project.create(root / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    bar = MeasurementTargetBar(ctl)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)

    mast = MastheadHeader(version="9.9.9")
    mast.set_center_widget(bar)
    mast.resize(1200, mast.sizeHint().height())
    mast.reposition_center()

    assert bar.sizeHint().height() > 28, "the bar is the two-line one"
    _assert_center_fits(mast)
    assert bar._location.text().endswith("runs/run1/")


# ---- left-anchored, not centred (Knut, #130 2026-07-26) -------------------
def _mast_with_bar(tmp_path, name="P", dates=()):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"),
                                         QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / name, name)
    run = proj.current_run(); run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    for d in dates:
        run.verification(d).ensure_dir()
    fm.set_target_name(name)
    ctl = MeasurementTargetController(fm)
    bar = MeasurementTargetBar(ctl)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    mast = MastheadHeader(version="9.9.9")
    mast.set_center_widget(bar)
    mast.resize(1200, mast.sizeHint().height())
    # Shown, as it is in the real window: Qt defers layout for hidden widgets,
    # so a hidden masthead would not exercise the re-layout path at all.
    mast.show()
    mast.reposition_center()
    return mast, bar, ctl


def test_the_bar_sits_just_right_of_the_printer_profiling_tag(qapp, tmp_path):
    """Knut asked for it left-adjusted against that text, not centred."""
    mast, bar, _ctl = _mast_with_bar(tmp_path)
    tag_w, _ver_w = mast._rail_text_widths()
    assert 18 + tag_w <= bar.x() <= 18 + tag_w + 40, (
        f"bar at x={bar.x()}, tag ends at {18 + tag_w:.0f}")
    assert bar.x() < mast.width() // 3, "it must not be centred"


def test_the_bar_does_not_move_when_it_grows(qapp, tmp_path):
    """A centred widget slides sideways whenever its content changes — which is
    what made the group jump when Run type was switched."""
    from core.measurement_target import RUN_TYPE_VERIFICATION
    mast, bar, ctl = _mast_with_bar(tmp_path)
    before_x = bar.x()
    before_w = bar.width()

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    QApplication.processEvents()
    mast.reposition_center()

    assert bar.x() == before_x, "the group's left edge must stay put"
    assert bar.width() >= before_w, "the extra boxes extend it to the right"


def test_the_bar_never_reaches_the_version_text(qapp, tmp_path):
    """Left-anchoring must not let a long selection run under "v9.9.9"."""
    mast, bar, _ctl = _mast_with_bar(tmp_path, name="A-Very-Long-Printer-Name")
    bar._location.setText("ChromIQ/" + "a-long-folder-name/" * 8)
    QApplication.processEvents()
    mast.reposition_center()

    _tag_w, ver_w = mast._rail_text_widths()
    assert bar.x() + bar.width() <= mast.width() - ver_w - 18


# ---- the centre widget must never overlap itself (Knut, #130 2026-07-26) ---
def _row_overlaps(bar):
    """Adjacent widgets in the bar's top row that intrude on one another."""
    row = bar.layout().itemAt(0).layout()
    visible = [row.itemAt(i).widget() for i in range(row.count())
               if row.itemAt(i).widget() is not None
               and row.itemAt(i).widget().isVisible()]
    visible.sort(key=lambda w: w.x())
    return [(type(a).__name__, type(b).__name__)
            for a, b in zip(visible, visible[1:])
            if a.x() + a.width() > b.x()]


def test_the_bar_is_relaid_the_moment_its_content_changes(qapp, tmp_path):
    """The regression Knut hit in beta.26: the rail is positioned by hand, so
    nothing re-laid the bar when *it* grew. Switching Run type left it at its
    old width and its children overlapped — "chaos" — until some later event
    happened to re-lay it. Nothing here calls reposition_center(): the masthead
    has to notice on its own."""
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.styles import APP_STYLESHEET
    mast, bar, ctl = _mast_with_bar(tmp_path)
    bar.setStyleSheet(APP_STYLESHEET)          # the padding is part of the fit
    QApplication.processEvents()
    assert not _row_overlaps(bar), "the bar starts out overlapping"

    ctl.set_run_type(RUN_TYPE_VERIFICATION)    # the very first change
    QApplication.processEvents()
    bar.layout().activate()

    assert bar.width() >= bar.minimumSizeHint().width(), (
        f"the bar is {bar.width()}px but needs {bar.minimumSizeHint().width()}px "
        f"— its children have nowhere to go but on top of each other")
    assert not _row_overlaps(bar), _row_overlaps(bar)


def test_no_overlap_through_a_run_of_changes(qapp, tmp_path):
    """Knut also had it come right "after a few changes" — so every step of a
    realistic sequence is checked, not just the end state."""
    from core.measurement_target import (RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from ui.styles import APP_STYLESHEET
    mast, bar, ctl = _mast_with_bar(tmp_path)
    bar.setStyleSheet(APP_STYLESHEET)

    for step in (lambda: ctl.set_run_type(RUN_TYPE_VERIFICATION),
                 lambda: ctl.set_run_type(RUN_TYPE_PROFILING),
                 lambda: ctl.set_profile_run(""),
                 lambda: ctl.set_run_type(RUN_TYPE_VERIFICATION),
                 lambda: ctl.set_profile_run("run1")):
        step()
        QApplication.processEvents()
        bar.layout().activate()
        assert not _row_overlaps(bar), _row_overlaps(bar)
        assert bar.width() >= bar.minimumSizeHint().width()


def test_a_narrow_rail_squeezes_the_bar_instead_of_letting_it_overrun(qapp,
                                                                      tmp_path):
    """With more to show than the rail can hold, the widest box gives up width
    — the bar never runs under the version text, and never over itself."""
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # layout pivots on real text widths
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.styles import APP_STYLESHEET
    mast, bar, ctl = _mast_with_bar(
        tmp_path, dates=("2026-07-20_100000", "2026-07-22_143000"))
    bar.setStyleSheet(APP_STYLESHEET)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    QApplication.processEvents()

    mast.resize(1180, mast.sizeHint().height())     # deliberately tight
    mast.reposition_center()
    QApplication.processEvents()
    bar.layout().activate()

    _tag_w, ver_w = mast._rail_text_widths()
    assert bar.x() + bar.width() <= mast.width() - ver_w - 18, \
        "the bar ran under the version text"
    assert not _row_overlaps(bar), _row_overlaps(bar)
    # The comfortable floor yields to the no-overrun rule when the two cannot
    # both be had (#130, 2026-07-28): the Delete button and its ⓘ cost about
    # 110 px, which a 1180 px window does not have spare. Running under the
    # version text is the beta.29 fault and is never acceptable; an elided date
    # still reads as a date, so THAT is what gives. The hard floor keeps a box
    # from collapsing to nothing.
    assert bar._verify_combo.width() >= bar._SQUEEZE_HARD_FLOOR, \
        "a box was squeezed past the point of being usable at all"


def test_the_comfortable_width_comes_back_when_there_is_room(qapp, tmp_path):
    """Squeezing is a concession to a narrow window, not a new normal."""
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # layout pivots on real text widths
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.styles import APP_STYLESHEET
    mast, bar, ctl = _mast_with_bar(
        tmp_path, dates=("2026-07-20_100000", "2026-07-22_143000"))
    bar.setStyleSheet(APP_STYLESHEET)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    QApplication.processEvents()

    # reposition_center() is called explicitly here because the offscreen
    # platform does not reliably deliver a resize to a top-level window; the
    # real window reaches the same code from MastheadHeader.resizeEvent.
    mast.resize(1180, mast.sizeHint().height())
    mast.reposition_center(); QApplication.processEvents()
    squeezed = bar._verify_combo.width()
    mast.resize(1800, mast.sizeHint().height())
    mast.reposition_center(); QApplication.processEvents()
    bar.layout().activate()

    assert bar._verify_combo.width() > squeezed
    fm = bar._verify_combo.fontMetrics()
    widest = max(fm.horizontalAdvance(bar._verify_combo.itemText(i))
                 for i in range(bar._verify_combo.count()))
    assert bar._verify_combo.width() >= widest, \
        "with room to spare every entry must be fully readable again"
