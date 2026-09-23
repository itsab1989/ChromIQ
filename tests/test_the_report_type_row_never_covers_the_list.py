"""B8-921: the "Report type" row covered the bottom of the measurement list.

Basti, 2026-09-23, on his own photograph of the Measurement Report window: the
fifth row of "Included Measurements in report" was half hidden behind the
"Report type" pulldown. Measured on screen (Report-Limits-Threshold-Series,
11 dated verifications), two faults:

* the list was sized to its rows **plus 4 px**, and the viewport is the list
  minus its frame only, so a sixth row showed a 4 px sliver under the fifth;
* ``showEvent`` fits the window to the screen once, with the list compacted,
  and asked ``minimumSize``, which does not count the wrapped labels. Picking
  a report rebuilt the list at five rows afterwards: the layout needed 1083 px
  in a window capped at 1039, Qt squeezed the "Report settings" frame below
  its minimum, and the pulldown, which cannot shrink, sat 8 px over the list
  (12 px at the minimum width).

This asks both questions at the window's default width, its minimum width and
Basti's (979 px), at the smallest height the window allows and at its ceiling,
by laying the window's own layout out at that size: the offscreen platform
ignores ``resize``, and a layout given a rectangle distributes it exactly as a
window of that size does.

MUTATIONS (both proven red):
* put ``+ 4`` back on ``frame`` in ``_size_profile_list``: a cut row;
* make ``_keep_the_list_inside_the_window`` return at once: widgets overlap.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPoint, QRect                     # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

_FRAME_WIDGETS = ("_add_btn", "_remove_btn", "_clear_btn", "_list_label",
                  "_profile_list", "_select_all_btn", "_deselect_all_btn",
                  "_type_label", "_type_combo", "_judged_label", "_set_combo")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def report_window(qapp, tmp_path):
    import os as _os
    import time as _time
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, _fm, _ctl, run = _verify_env(tmp_path)
    for i in range(11):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES),
                                     encoding="utf-8")
        t = _time.time() - 3600 + i * 60
        _os.utime(v.measurement_ti3, (t, t))
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(
        s, None, initial_ti3=run.verifications()[0].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    # what picking a report does after the window is on screen: the list is
    # built again at its full five rows
    dlg._rebuild_from_sources()
    for _ in range(5):
        qapp.processEvents()
    yield dlg
    dlg.hide()
    dlg.deleteLater()


def _faults(dlg, w: int, h: int) -> "list[str]":
    lay = dlg.layout()
    lay.setGeometry(QRect(0, 0, w, h))
    QApplication.processEvents()
    out = []
    rects = {}
    for name in _FRAME_WIDGETS:
        wd = getattr(dlg, name)
        if wd.isVisible():
            rects[name] = QRect(wd.mapTo(dlg, QPoint(0, 0)), wd.size())
    names = list(rects)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if rects[a].intersects(rects[b]):
                out.append(f"{a} {rects[a].getRect()} overlaps "
                           f"{b} {rects[b].getRect()}")
    lst = dlg._profile_list
    vp_h = lst.viewport().height()
    for i in range(lst.count()):
        r = lst.visualItemRect(lst.item(i))
        if r.top() + r.height() <= 0 or r.top() >= vp_h:
            continue                                  # not on screen at all
        if r.top() < 0 or r.top() + r.height() > vp_h:
            out.append(f"row {i} is cut: rows {r.top()}..{r.top() + r.height()}"
                       f" in a {vp_h} px viewport")
    return out


def test_no_control_of_the_settings_frame_covers_another(report_window):
    dlg = report_window
    assert dlg._profile_list.count() == 12, "the premise: more than five rows"
    default_w = dlg.width()
    floor_w = max(dlg.minimumWidth(), dlg.layout().minimumSize().width())
    lo = dlg.minimumHeight()
    hi = dlg.maximumHeight()
    assert hi < 16777215, "showEvent put no ceiling on the window"
    faults = []
    for w in sorted({default_w, floor_w, 979}):
        for h in sorted({lo, hi}):
            faults += [f"{w}x{h}: {f}" for f in _faults(dlg, w, h)]
    assert not faults, "\n".join(faults)


def test_the_list_shows_whole_rows_and_scrolls_for_the_rest(report_window):
    lst = report_window._profile_list
    shown = report_window._list_rows_shown
    assert 2 <= shown <= report_window._LIST_VISIBLE_ROWS
    rows = sum(lst.sizeHintForRow(i) for i in range(shown))
    assert lst.maximumHeight() == rows + 2 * lst.frameWidth(), (
        "the list is sized to something other than its whole rows")
