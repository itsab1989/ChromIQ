"""B8-956 (beta 41): at every size the Measurement Report window allows, the
measurement list shows at least two whole rows and Select all / Deselect all
keep their natural height, EN and DE.

Measured on screen at beta 40 (``~/Desktop/ChromIQ-beta40-proof/second-check/
a4-en``, ``a4-de``, ``*-3-minimum-size.png``): at the 760 px minimum size the
list showed one date under its heading, and the two buttons beside it were
squashed to about half their height with the text touching the frame. B8-590
had capped the buttons to a list compacted to two rows. Now the list never
goes below the buttons' column (`_list_box`), and the window's fitting gives
up the report view first (its last rung, 60 px).

The window is laid out the way `test_the_report_type_row_never_covers_the_
list` does it: its own layout given a rectangle, at the smallest height the
window allows and at its ceiling, at its default, minimum and 979 px widths.

MUTATION, proven red (~/Desktop/ChromIQ-beta41-proof/small-fixes/): make
`_list_box` return ``rows, h`` (no floor for the buttons' column) and cap the
buttons to the list again.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPoint, QRect                     # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core import i18n                                      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


#: (dates, language, ceiling): None is the offscreen screen's own (800 px,
#: capped at 760), 1039 the owner's screen, where the beta 40 photographs
#: were taken (a4-en driver-notes: "dialog 760x1039"). German is asked at
#: 1039 only: at 760 px wide its "Report settings" frame alone needs 233 px
#: (its button rows wrap), and the window does not fit an 800 px screen
#: whatever the list does (B8-956, note).
_CASES = [(1, "en", None), (11, "en", None), (1, "en", 1039),
          (11, "en", 1039), (2, "de", 1039), (11, "de", 1039)]


@pytest.fixture(params=_CASES,
                ids=[f"{n}-dates-{lang}-{cap or 'screen'}"
                     for n, lang, cap in _CASES])
def report_window(request, qapp, tmp_path):
    import time as _time
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    dates, lang, ceiling = request.param
    before = i18n.current_language() if hasattr(i18n, "current_language") \
        else "en"
    i18n.set_language(lang)
    try:
        s, _fm, _ctl, run = _verify_env(tmp_path)
        for i in range(dates):
            v = run.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES),
                                         encoding="utf-8")
            t = _time.time() - 3600 + i * 60
            os.utime(v.measurement_ti3, (t, t))
        from ui.dialogs.measurement_report_dialog import \
            MeasurementReportDialog
        dlg = MeasurementReportDialog(
            s, None, initial_ti3=run.verifications()[0].measurement_ti3)
        dlg.show()
        qapp.processEvents()
        dlg._rebuild_from_sources()
        for _ in range(5):
            qapp.processEvents()
        if ceiling:
            # the owner's screen: the ceiling `showEvent` would have set there
            dlg.setMaximumHeight(ceiling)
            dlg._keep_the_list_inside_the_window()
            for _ in range(5):
                qapp.processEvents()
        yield dlg
        dlg.hide()
        dlg.deleteLater()
    finally:
        i18n.set_language(before or "en")


def _faults(dlg, w: int, h: int) -> "list[str]":
    lay = dlg.layout()
    lay.setGeometry(QRect(0, 0, w, h))
    QApplication.processEvents()
    out = []
    lst = dlg._profile_list
    for b in (dlg._select_all_btn, dlg._deselect_all_btn):
        natural = max(b.sizeHint().height(), b.minimumSizeHint().height())
        if b.height() < natural:
            out.append(f"{w}x{h}: {b.text()!r} is {b.height()} of its "
                       f"{natural} px")
    # whole rows the viewport shows
    vp_h = lst.viewport().height()
    whole = 0
    for i in range(lst.count()):
        r = lst.visualItemRect(lst.item(i))
        if r.top() >= 0 and r.top() + r.height() <= vp_h:
            whole += 1
    if whole < min(2, lst.count()):
        out.append(f"{w}x{h}: the list shows {whole} whole row(s) of "
                   f"{lst.count()}")
    # nothing below the list covers it or the buttons
    rect = {n: QRect(getattr(dlg, n).mapTo(dlg, QPoint(0, 0)),
                     getattr(dlg, n).size())
            for n in ("_profile_list", "_select_all_btn",
                      "_deselect_all_btn", "_type_combo", "_type_label")}
    for a in ("_profile_list", "_select_all_btn", "_deselect_all_btn"):
        for b in ("_type_combo", "_type_label"):
            if rect[a].intersects(rect[b]):
                out.append(f"{w}x{h}: {a} {rect[a].getRect()} overlaps "
                           f"{b} {rect[b].getRect()}")
    return out


def test_the_list_and_its_buttons_keep_their_height_at_every_size(
        report_window):
    dlg = report_window
    lo = dlg.minimumHeight()
    hi = dlg.maximumHeight()
    assert hi < 16777215, "showEvent put no ceiling on the window"
    floor_w = max(dlg.minimumWidth(), dlg.layout().minimumSize().width())
    faults = []
    for w in sorted({dlg.width(), floor_w, 979}):
        for h in sorted({lo, (lo + hi) // 2, hi}):
            faults += _faults(dlg, w, h)
    assert not faults, "\n".join(faults)


def test_the_list_is_never_lower_than_the_buttons_beside_it(report_window):
    dlg = report_window
    col = dlg._tick_column_height()
    assert col >= 2 * dlg._select_all_btn.sizeHint().height()
    assert dlg._profile_list.minimumHeight() >= col
    for rows in (1, 2, 3):
        assert dlg._list_box(rows)[1] >= col
