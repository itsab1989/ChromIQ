"""4.3.32: files dragged from the file manager onto Tools > Measurement info
(jctay, forum post 150152: "would it be possible to add drag-and-drop for
selecting files?").

Pinned here:
* the Other readings row takes one file or several, exactly as Add… does:
  the same list, the same limit of nine (files past it are not added and the
  banner says how many), a file already listed is not added twice, another
  chart is refused in the same words;
* a folder, a web link and a file of another kind are left out; a drag of
  nothing usable is not accepted at all (no highlight, no change);
* paths with spaces and umlauts arrive intact, and a Windows file URL
  (``file:///C:/...``) is read as a drive path on every platform;
* the highlight shows while a usable drag hovers and is gone on leave and on
  drop, in the window's accent (Neutral: the ACTION ink);
* one .ti3 dropped on the Measurement row opens it, as Browse does; two
  files there are not accepted;
* the drop is routed by Qt itself: events sent to the WINDOW reach the row
  under the pointer (neither the read-only field nor the list swallows them);
* the handlers are overrides and the delivery a bound method, and the load
  happens after the drop returns, not inside it.

Fixtures are the suite's own ET-8550 reading with noise
(`tests/test_4332_compare_two_readings.py`).
"""
from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PyQt6.QtGui import (QDragEnterEvent, QDragLeaveEvent,  # noqa: E402
                         QDragMoveEvent, QDropEvent)
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests.test_4332_compare_two_readings import (  # noqa: E402
    _inspector, _noisy, _texts, _write)
from ui.file_drop import FileDropZone, paths_from_mime  # noqa: E402
from workflow import measurement_messages as M  # noqa: E402
from workflow.reading_compare import MAX_OTHER_READINGS  # noqa: E402


def _same(rows, fields):
    return rows


def _mime(*items) -> QMimeData:
    m = QMimeData()
    m.setUrls([i if isinstance(i, QUrl) else QUrl.fromLocalFile(str(i))
               for i in items])
    return m


_KEEP = []   # the mime data must outlive the events that point at it


def _drag(zone, mime, *, drop=True, qapp=None):
    """Enter, move and (optionally) drop *mime* in the middle of *zone*,
    sent to the zone itself. Returns (accepted on enter, highlighted after
    enter)."""
    _KEEP.append(mime)
    c = zone.rect().center()
    act = Qt.DropAction.CopyAction
    btn = Qt.MouseButton.LeftButton
    mod = Qt.KeyboardModifier.NoModifier
    enter = QDragEnterEvent(c, act, mime, btn, mod)
    QApplication.sendEvent(zone, enter)
    accepted = enter.isAccepted()
    if accepted:
        QApplication.sendEvent(zone, QDragMoveEvent(c, act, mime, btn, mod))
    lit = zone.is_highlighted()
    if drop and accepted:
        QApplication.sendEvent(zone, QDropEvent(QPointF(c), act, mime, btn,
                                                mod))
        if qapp is not None:
            for _ in range(3):
                qapp.processEvents()
    return accepted, lit


@pytest.fixture
def a(tmp_path):
    return _write(tmp_path / "a.ti3", _same)


def _others(dlg):
    return [p.name for p in dlg._others]


# ---- paths -----------------------------------------------------------------

def test_spaces_and_umlauts_arrive_intact(tmp_path):
    d = tmp_path / "Messungen Jürgen ÄÖÜ ß"
    d.mkdir()
    f = d / "zweite Messung (Glänzend).ti3"
    f.write_text("x", encoding="utf-8")
    url = QUrl.fromLocalFile(str(f))
    assert "%20" in url.toString(QUrl.ComponentFormattingOption.FullyEncoded)
    got, left = paths_from_mime(_mime(url), (".ti3",))
    assert got == [f] and left == 0
    # and from the encoded text form a file manager hands over
    enc = QUrl(url.toString(QUrl.ComponentFormattingOption.FullyEncoded))
    got, _ = paths_from_mime(_mime(enc), (".ti3",))
    assert got == [f]


@pytest.mark.parametrize("url, want", [
    ("file:///C:/Users/J%C3%BCrgen/My%20Readings/second%20read.ti3",
     "C:/Users/Jürgen/My Readings/second read.ti3"),
    ("file:///D:/a.TI3", "D:/a.TI3"),
    ("file://server/share/Readings/a.ti3", "//server/share/Readings/a.ti3"),
])
def test_a_windows_file_url_is_a_drive_path_on_every_platform(url, want):
    got, left = paths_from_mime(_mime(QUrl(url)), (".ti3",),
                                check_disk=False)
    assert left == 0 and [p.as_posix() for p in got] == [Path(want).as_posix()]


def test_folders_links_and_other_kinds_are_left_out(tmp_path):
    good = tmp_path / "b.CXF"
    good.write_text("x", encoding="utf-8")
    pdf = tmp_path / "notes.pdf"
    pdf.write_text("x", encoding="utf-8")
    folder = tmp_path / "folder.ti3"     # a folder that LOOKS like a file
    folder.mkdir()
    gone = tmp_path / "missing.ti3"
    got, left = paths_from_mime(
        _mime(good, pdf, folder, gone, QUrl("https://example.org/a.ti3")),
        (".ti3", ".cxf"))
    assert got == [good] and left == 4


# ---- the Other readings row ------------------------------------------------

def test_one_dropped_reading_is_added_as_add_adds_it(qapp, a, tmp_path):
    b = _write(tmp_path / "b.ti3", _noisy(bad=(10, 200)))
    dlg = _inspector(qapp, a)
    ok, lit = _drag(dlg._others_zone, _mime(b), qapp=qapp)
    assert ok and lit
    assert _others(dlg) == ["b.ti3"]
    assert "Another reading of this chart" in _texts(dlg)
    assert not dlg._others_zone.is_highlighted()
    dlg.deleteLater()


def test_several_dropped_readings_are_added_in_order(qapp, a, tmp_path):
    bs = [_write(tmp_path / f"r{k}.ti3", _noisy(seed=k)) for k in range(3)]
    dlg = _inspector(qapp, a)
    _drag(dlg._others_zone, _mime(*bs), qapp=qapp)
    assert _others(dlg) == ["r0.ti3", "r1.ti3", "r2.ti3"]
    assert "Other readings of this chart" in _texts(dlg)
    dlg.deleteLater()


def test_a_mix_adds_only_the_readings(qapp, a, tmp_path):
    b = _write(tmp_path / "b.ti3", _noisy())
    pdf = tmp_path / "notes.pdf"
    pdf.write_text("x", encoding="utf-8")
    folder = tmp_path / "more"
    folder.mkdir()
    dlg = _inspector(qapp, a)
    ok, _ = _drag(dlg._others_zone, _mime(pdf, b, folder), qapp=qapp)
    assert ok and _others(dlg) == ["b.ti3"]
    dlg.deleteLater()


def test_nothing_usable_is_not_accepted(qapp, a, tmp_path):
    pdf = tmp_path / "notes.pdf"
    pdf.write_text("x", encoding="utf-8")
    folder = tmp_path / "Readings"
    folder.mkdir()
    dlg = _inspector(qapp, a)
    for mime in (_mime(pdf), _mime(folder), _mime(pdf, folder)):
        ok, lit = _drag(dlg._others_zone, mime, qapp=qapp)
        assert not ok and not lit
    text = QMimeData()
    text.setText("hello")
    ok, lit = _drag(dlg._others_zone, text, qapp=qapp)
    assert not ok and not lit
    assert dlg._others == [] and not dlg._banner.isVisibleTo(dlg)
    dlg.deleteLater()


def test_a_duplicate_is_not_added_twice(qapp, a, tmp_path):
    b = _write(tmp_path / "b.ti3", _noisy())
    dlg = _inspector(qapp, a)
    dlg.add_readings([b])
    _drag(dlg._others_zone, _mime(b, b), qapp=qapp)
    assert _others(dlg) == ["b.ti3"]
    dlg.deleteLater()


def test_past_the_limit_the_rest_is_not_added_and_said(qapp, a, tmp_path):
    bs = [_write(tmp_path / f"r{k:02d}.ti3", _noisy(seed=k))
          for k in range(MAX_OTHER_READINGS + 3)]
    dlg = _inspector(qapp, a)
    dlg.add_readings(bs[:2])
    _drag(dlg._others_zone, _mime(*bs[2:]), qapp=qapp)
    assert len(dlg._others) == MAX_OTHER_READINGS
    assert _others(dlg) == [p.name for p in bs[:MAX_OTHER_READINGS]]
    assert dlg._banner.isVisibleTo(dlg)
    assert ("3 of the files you chose were not added"
            in dlg._banner.text())
    dlg.deleteLater()


def test_another_chart_dropped_is_refused_in_the_same_words(qapp, a,
                                                            tmp_path):
    b = _write(tmp_path / "b.ti3", lambda r, f: r[:-1])
    dlg = _inspector(qapp, a)
    _drag(dlg._others_zone, _mime(b), qapp=qapp)
    title, _body = M.M_READINGS_NOT_SAME_CHART.render(file="b.ti3",
                                                      reason="x")
    assert title in _texts(dlg) and _others(dlg) == ["b.ti3"]
    dlg.deleteLater()


def test_a_drop_before_any_measurement_is_kept_as_add_keeps_it(qapp,
                                                               tmp_path):
    from tests.test_profile_tools import _runner, _Settings
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    b = _write(tmp_path / "b.ti3", _noisy())
    dlg = Ti3InfoDialog(_runner(), _Settings())
    _drag(dlg._others_zone, _mime(b), qapp=qapp)
    assert _others(dlg) == ["b.ti3"]
    dlg.deleteLater()


def test_a_path_with_spaces_and_umlauts_is_added(qapp, a, tmp_path):
    d = tmp_path / "Zweite Messung Jürgen"
    d.mkdir()
    b = _write(d / "Glänzend Papier 2.ti3", _noisy())
    dlg = _inspector(qapp, a)
    _drag(dlg._others_zone, _mime(b), qapp=qapp)
    assert dlg._others == [b]
    dlg.deleteLater()


# ---- highlight -------------------------------------------------------------

def test_the_highlight_goes_on_leave(qapp, a, tmp_path):
    b = _write(tmp_path / "b.ti3", _noisy())
    dlg = _inspector(qapp, a)
    zone = dlg._others_zone
    ok, lit = _drag(zone, _mime(b), drop=False)
    assert ok and lit and zone._overlay.isVisibleTo(zone)
    QApplication.sendEvent(zone, QDragLeaveEvent())
    assert not zone.is_highlighted() and dlg._others == []
    dlg.deleteLater()


@pytest.mark.parametrize("appearance, want", [
    ("light", "#37bcd6"), ("dark", "#37bcd6"), ("neutral", None)])
def test_the_highlight_takes_the_window_accent(qapp, appearance, want):
    from tests.test_profile_tools import _runner, _Settings
    from ui import neutral_styles
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    s = _Settings()
    s.set("appearance", appearance)
    dlg = Ti3InfoDialog(_runner(), s)
    want = want or neutral_styles.NM_ACTION
    for zone in (dlg._pick_zone, dlg._others_zone):
        assert zone._overlay.colour.lower() == want.lower()
    dlg.deleteLater()


# ---- the Measurement row ---------------------------------------------------

def test_one_ti3_dropped_on_the_measurement_row_opens_it(qapp, a, tmp_path):
    b = _write(tmp_path / "b ö.ti3", _noisy())
    dlg = _inspector(qapp, a)
    ok, lit = _drag(dlg._pick_zone, _mime(b), qapp=qapp)
    assert ok and lit
    assert dlg._path_edit.text() == str(b)
    assert dlg._analysis is not None and dlg._analysis.data.path == b
    assert "b ö.ti3" in dlg._body.text()
    assert not dlg._pick_zone.is_highlighted()
    dlg.deleteLater()


def test_the_measurement_row_takes_one_ti3_only(qapp, a, tmp_path):
    b = _write(tmp_path / "b.ti3", _noisy())
    c = _write(tmp_path / "c.ti3", _noisy(seed=3))
    txt = tmp_path / "b.txt"
    txt.write_text("x", encoding="utf-8")
    dlg = _inspector(qapp, a)
    for mime in (_mime(b, c), _mime(txt), _mime(tmp_path)):
        ok, lit = _drag(dlg._pick_zone, mime, qapp=qapp)
        assert not ok and not lit
    assert dlg._path_edit.text() == str(a)
    dlg.deleteLater()


# ---- routed by Qt, as a real drag is ---------------------------------------

@pytest.mark.parametrize("target", ["_others_list", "_others_empty",
                                    "_second_browse", "_path_edit"])
def test_a_drag_sent_to_the_window_reaches_the_row(qapp, a, tmp_path, target):
    """The window's own drag handling picks the widget under the pointer and
    walks up to the first that accepts drops: neither the read-only field
    nor the list may take (and refuse) the drag first."""
    b = _write(tmp_path / "b.ti3", _noisy())
    dlg = _inspector(qapp, a)
    if target == "_others_list":
        dlg.add_readings([_write(tmp_path / "c.ti3", _noisy(seed=4))])
    dlg.resize(900, 900)
    dlg.show()
    qapp.processEvents()
    w = getattr(dlg, target)
    assert w.isVisible()
    zone = dlg._pick_zone if target == "_path_edit" else dlg._others_zone
    pos = w.mapTo(dlg, w.rect().center())
    win = dlg.windowHandle()
    mime = _mime(b)
    _KEEP.append(mime)
    act = Qt.DropAction.CopyAction
    btn = Qt.MouseButton.LeftButton
    mod = Qt.KeyboardModifier.NoModifier
    enter = QDragEnterEvent(QPoint(pos), act, mime, btn, mod)
    QApplication.sendEvent(win, enter)
    QApplication.sendEvent(win, QDragMoveEvent(QPoint(pos), act, mime, btn,
                                               mod))
    assert zone.is_highlighted()
    QApplication.sendEvent(win, QDropEvent(QPointF(pos), act, mime, btn, mod))
    for _ in range(3):
        qapp.processEvents()
    assert not zone.is_highlighted()
    if target == "_path_edit":
        assert dlg._path_edit.text() == str(b)
    else:
        assert b in dlg._others
    dlg.close()
    dlg.deleteLater()


# ---- the safety rules ------------------------------------------------------

def test_the_drop_loads_after_the_drop_returns(qapp, a, tmp_path):
    """On macOS a drop is delivered inside the system's drag session; the
    load happens on the next turn of the event loop, never inside it."""
    b = _write(tmp_path / "b.ti3", _noisy())
    dlg = _inspector(qapp, a)
    zone = dlg._others_zone
    mime = _mime(b)
    _KEEP.append(mime)
    c = zone.rect().center()
    act = Qt.DropAction.CopyAction
    btn = Qt.MouseButton.LeftButton
    mod = Qt.KeyboardModifier.NoModifier
    QApplication.sendEvent(zone, QDragEnterEvent(c, act, mime, btn, mod))
    drop = QDropEvent(QPointF(c), act, mime, btn, mod)
    QApplication.sendEvent(zone, drop)
    assert drop.isAccepted() and dlg._others == []
    for _ in range(3):
        qapp.processEvents()
    assert dlg._others == [b]
    dlg.deleteLater()


def test_no_lambda_no_wait_cursor_in_the_drop_code():
    import ui.file_drop as fd
    from ui.dialogs import ti3_info_dialog as ti
    lam = re.compile(r"\blambda\b(?!s)")
    src = inspect.getsource(fd)
    assert not lam.search(src) and "WaitCursor" not in src
    for name in ("_on_readings_dropped", "_on_measurement_dropped"):
        body = inspect.getsource(getattr(ti.Ti3InfoDialog, name))
        assert not lam.search(body) and "WaitCursor" not in body
    init = inspect.getsource(ti.Ti3InfoDialog)
    assert "files_dropped.connect(self._on_readings_dropped)" in init
    assert "files_dropped.connect(self._on_measurement_dropped)" in init
    for meth in ("dragEnterEvent", "dragMoveEvent", "dragLeaveEvent",
                 "dropEvent"):
        assert meth in FileDropZone.__dict__
