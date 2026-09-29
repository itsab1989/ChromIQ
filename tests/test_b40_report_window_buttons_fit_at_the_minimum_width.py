"""B8-927 (beta 40): nothing in the Measurement Report window's settings and
action rows overlaps or is cut at its 760 px minimum width, EN or DE.

Measured on screen at 16da4232 (``~/Desktop/ChromIQ-beta40-proof/small-fixes/
before/MIN-*/geometry-*.json``), window 760 px wide:

* German "Messungen eines Profils hinzufügen…" / "…entfernen…" / "Liste
  leeren" asked 759 px of the frame's 694 and were drawn over each other;
* the four action buttons asked 857 px (German) and 719 (English) of 716:
  "Ausgewählten Bericht löschen" under "Bericht als PDF speichern…" (the
  beta 39 photograph G3-why-minimum.png), "Delete Selected Report" under
  "Save report as PDF…";
* "Show detailed data for each run" had 205 of its 220 px, "Detaildaten für
  jeden Lauf anzeigen" 216 of 243.

The window's hard minimum (760) is below what the one-line rows ask, so Qt
squeezed them. The three rows are now `ui.widgets.ReflowRow`s: a group that
does not fit starts a second line. ("Grenzwerte bearbeiten…" fits since K31
removed the Unlock box: 215 of 215 px.)

The window is laid out the way `test_the_report_type_row_never_covers_the_
list` does it (the offscreen platform ignores ``resize``); a row given less
than one line needs is asked for directly as well, because offscreen font
metrics are not the screen's.

MUTATION, proven red: make `ReflowRow._split` return every group on one
line (``return [list(range(len(self._groups)))]``).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPoint, QRect                     # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox,      # noqa: E402
                             QPushButton, QWidget)

from core import i18n                                      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=["en", "de"])
def report_window(request, qapp, tmp_path):
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    before = i18n.current_language() if hasattr(i18n, "current_language") \
        else "en"
    i18n.set_language(request.param)
    try:
        s, _fm, _ctl, run = _verify_env(tmp_path)
        for _ in range(2):
            v = run.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES),
                                         encoding="utf-8")
        from ui.dialogs.measurement_report_dialog import \
            MeasurementReportDialog
        dlg = MeasurementReportDialog(
            s, None, initial_ti3=run.verifications()[0].measurement_ti3)
        dlg.show()
        qapp.processEvents()
        yield dlg
        dlg.hide()
        dlg.deleteLater()
    finally:
        i18n.set_language(before or "en")


def _rows(dlg):
    return (dlg._add_reflow, dlg._type_tail_reflow, dlg._actions_reflow)


def _lay_out(dlg, w):
    # the offscreen screen is 760 px tall and the window is capped to it; a
    # real screen's height, so the rows are asked about width alone
    dlg.setMaximumHeight(1400)
    dlg.resize(w, 1400)
    for _ in range(4):
        QApplication.processEvents()


def _kids(row):
    return [c for c in row.findChildren(QWidget)
            if c.isVisible() and c.parentWidget() is row]


def _faults(dlg) -> "list[str]":
    """Inside each of the three rows: a button or check box narrower than
    its text asks, or two controls on top of each other. (Between the rows
    is `test_the_report_type_row_never_covers_the_list`'s question; the
    offscreen screen is too short to ask it here.)"""
    out = []
    for row in _rows(dlg):
        ws = _kids(row)
        for w in ws:
            if isinstance(w, (QPushButton, QCheckBox)) and \
                    w.width() < w.sizeHint().width():
                out.append(f"{w.text()!r} cut: {w.width()} of "
                           f"{w.sizeHint().width()} px")
        for i, a in enumerate(ws):
            for b in ws[i + 1:]:
                if a.geometry().intersects(b.geometry()):
                    out.append(f"{getattr(a, 'text', str)()!r} "
                               f"{a.geometry().getRect()} overlaps "
                               f"{getattr(b, 'text', str)()!r} "
                               f"{b.geometry().getRect()}")
        right = max((w.geometry().right() for w in ws), default=0)
        if right >= row.width():
            out.append(f"a control reaches x={right} in a {row.width()} px "
                       "row")
    return out


def test_nothing_overlaps_or_is_cut_at_the_minimum_width(report_window):
    dlg = report_window
    assert dlg.minimumWidth() == 760
    wide = dlg.width()
    for w in (760, wide):
        _lay_out(dlg, w)
        assert dlg.width() == w
        assert not _faults(dlg), f"at {w} px:\n" + "\n".join(_faults(dlg))


def test_a_row_too_short_for_one_line_takes_two(qapp):
    """The row itself, in a host of a chosen width: one line while it fits,
    two when it does not, back to one when it fits again, and a group is
    never split."""
    from PyQt6.QtWidgets import QVBoxLayout
    from ui.widgets import ReflowRow
    host = QWidget()
    QVBoxLayout(host).setContentsMargins(0, 0, 0, 0)
    row = ReflowRow(host)
    a, b, c = (QPushButton(t) for t in ("Messungen eines Profils hinzufügen…",
                                        "Messungen eines Profils entfernen…",
                                        "Liste leeren"))
    icon = QPushButton("i")
    row.add_group(a)
    row.add_group(b)
    row.add_group(c, icon)
    host.layout().addWidget(row)
    one = sum(row._group_width(g) for g in row._groups) + 2 * 6
    try:
        for width, lines in ((one + 40, 1), (one - 40, 2), (one + 40, 1)):
            host.resize(width, 200)
            host.show()
            for _ in range(4):
                qapp.processEvents()
            assert row.lines() == lines, (width, row.lines())
            ws = _kids(row)
            for i, x in enumerate(ws):
                assert x.width() >= x.sizeHint().width(), x.text()
                for y in ws[i + 1:]:
                    assert not x.geometry().intersects(y.geometry())
            assert abs(c.geometry().y() - icon.geometry().y()) < c.height()
    finally:
        host.hide()
        host.deleteLater()
