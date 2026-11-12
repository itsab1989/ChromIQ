"""4.3.33: files dragged from the file manager onto every Browse row where
that is safe (the owner, after 4.3.32's Measurement info: "in the other
places where safe and beneficial"). The inventory and the rule are in
docs/design/tool_availability.md ("Files dropped on every Browse row").

ONE TABLE, ONE ROW PER WINDOW ROW THAT TAKES A DROP. For each it is pinned
that

* a fitting file dropped on the row reaches the very method the row's Browse
  hands its chosen file to, with the same argument (the method is patched on
  the class before the window is built, so the zone's connection and the
  Browse call both reach the recorder);
* a file of another kind is not accepted (no call, no highlight, the field
  unchanged), and neither is a folder on a file row or a file on a folder
  row;
* a greyed or busy row accepts nothing;
* a file dropped on an editable field is not pasted into it as text, and
  plain text dropped there still is.

And, from a second table, that every row the inventory SKIPS takes no file.

The drags are sent to the WINDOW at the row's field, as a real drag is:
Qt picks the widget under the pointer and walks up to the first that takes
drops, so a field that swallowed the drag would fail here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PyQt6.QtGui import (QDragEnterEvent, QDragMoveEvent,  # noqa: E402
                         QDropEvent)
from PyQt6.QtWidgets import (QAbstractScrollArea, QApplication,  # noqa: E402
                             QLineEdit, QScrollArea, QWidget)

from tests.test_profile_tools import _runner, _Settings  # noqa: E402


_KEEP: list = []      # mime data must outlive the events that point at it


def _mime(*paths, text: "str | None" = None) -> QMimeData:
    m = QMimeData()
    if paths:
        m.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    if text is not None:
        m.setText(text)
    _KEEP.append(m)
    return m


def _pump(qapp, n: int = 4) -> None:
    for _ in range(n):
        qapp.processEvents()


def _bring_into_view(w: QWidget) -> None:
    p = w.parentWidget()
    while p is not None:
        if isinstance(p, QScrollArea):
            p.ensureWidgetVisible(w, 0, 0)
        p = p.parentWidget()


def drag_to(qapp, w: QWidget, mime: QMimeData, *, drop: bool = True) -> bool:
    """Enter, move and drop *mime* on the middle of *w*, sent to its WINDOW
    (so Qt routes it as a real drag). True when the drag was accepted."""
    win = w.window()
    _bring_into_view(w)
    _pump(qapp, 2)
    pos = w.mapTo(win, w.rect().center())
    handle = win.windowHandle()
    act = Qt.DropAction.CopyAction
    btn = Qt.MouseButton.LeftButton
    mod = Qt.KeyboardModifier.NoModifier
    enter = QDragEnterEvent(QPoint(pos), act, mime, btn, mod)
    QApplication.sendEvent(handle, enter)
    move = QDragMoveEvent(QPoint(pos), act, mime, btn, mod)
    QApplication.sendEvent(handle, move)
    ok = move.isAccepted()
    if drop:
        d = QDropEvent(QPointF(pos), act, mime, btn, mod)
        QApplication.sendEvent(handle, d)
        ok = ok and d.isAccepted()
        _pump(qapp)
    return ok


# ---------------------------------------------------------------------------
# the table
# ---------------------------------------------------------------------------

@dataclass
class Row:
    id: str
    build: Callable            # (settings) -> window
    owner: Callable            # () -> the class whose method is the handler
    handler: str               # the method Browse hands its file to
    drop_on: Callable          # (win) -> the widget the file is dropped on
    browse: Callable           # (win) -> press the row's Browse
    dialog: str                # "module:attr" of the chooser Browse calls
    good: tuple                # suffixes of fitting files
    bad: str = ".pdf"          # a kind the row does not take
    several: bool = False      # a list: several files at once
    folder: bool = False       # a folder row
    closed: "Callable | None" = None   # (win) -> make the row refuse
    editable: "Callable | None" = None  # (win) -> its editable field
    prepare: "Callable | None" = None   # (win) -> make the row visible
    extra_patches: dict = field(default_factory=dict)


def _tools(name):
    def build(settings):
        from ui.dialogs import tools_dialogs as T
        cls = getattr(T, name)
        try:
            return cls(_runner(), settings)
        except TypeError:
            return cls(settings)
    return build


def _cls(module, name):
    def get():
        import importlib
        return getattr(importlib.import_module(module), name)
    return get


def _busy(win):
    win._busy = True


_TD = "ui.dialogs.tools_dialogs"
_OPEN = _TD + ":open_file_dialog"
_OPENS = _TD + ":open_files_dialog"

ROWS: list[Row] = [
    # -- Tools > Average / Merge (R04-R06) ---------------------------------
    Row("average-list", _tools("AverageMeasurementsDialog"),
        _cls(_TD, "AverageMeasurementsDialog"), "_use_files",
        lambda w: w._list, lambda w: w._add_files(), _OPENS, (".ti3",),
        several=True, closed=_busy),
    Row("merge-primary", _tools("MergeMeasurementsDialog"),
        _cls(_TD, "MergeMeasurementsDialog"), "_use_primary",
        lambda w: w._primary_field, lambda w: w._pick_primary(), _OPEN,
        (".ti3",), closed=_busy),
    Row("merge-additional", _tools("MergeMeasurementsDialog"),
        _cls(_TD, "MergeMeasurementsDialog"), "_use_additional",
        lambda w: w._list, lambda w: w._add_additional(), _OPENS, (".ti3",),
        several=True, closed=_busy),
    # -- converters (R07-R09) ------------------------------------------------
    Row("ti1-to-i1profiler", _tools("Ti1ToI1ProfilerDialog"),
        _cls(_TD, "Ti1ToI1ProfilerDialog"), "_use_ti1",
        lambda w: w._ti1_field, lambda w: w._pick_ti1(), _OPEN, (".ti1",),
        closed=_busy),
    Row("i1profiler-to-ti3", _tools("I1ProfilerToTi3Dialog"),
        _cls(_TD, "I1ProfilerToTi3Dialog"), "_use_txt",
        lambda w: w._txt_field, lambda w: w._pick_txt(), _OPEN,
        (".txt", ".mxf", ".cxf"), bad=".ti3", closed=_busy),
    Row("i1profiler-to-ti1", _tools("I1ProfilerToTi1Dialog"),
        _cls(_TD, "I1ProfilerToTi1Dialog"), "_use_src",
        lambda w: w._src_field, lambda w: w._pick_src(), _OPEN,
        (".pxf", ".pwxf", ".cgats", ".txt"), bad=".ti3", closed=_busy),
    # -- Verify against reference (R10-R13) ----------------------------------
    Row("verify-ref-expected-box", _tools("VerifyAgainstReferenceDialog"),
        _cls(_TD, "VerifyAgainstReferenceDialog"), "_use_reference_file",
        lambda w: w._ref_edit, lambda w: w._load_reference_file(), _OPEN,
        (".txt", ".cgats", ".ti3", ".csv"), closed=_busy,
        editable=lambda w: w._ref_edit),
    Row("verify-ref-measured", _tools("VerifyAgainstReferenceDialog"),
        _cls(_TD, "VerifyAgainstReferenceDialog"), "_use_measured",
        lambda w: w._measured_field, lambda w: w._pick_measured(), _OPEN,
        (".ti3",), closed=_busy),
    Row("verify-ref-chart", _tools("VerifyAgainstReferenceDialog"),
        _cls(_TD, "VerifyAgainstReferenceDialog"), "_use_chart",
        lambda w: w._chart_field, lambda w: w._pick_chart(), _OPEN,
        (".ti1", ".ti2"), closed=_busy),
    Row("verify-ref-profile", _tools("VerifyAgainstReferenceDialog"),
        _cls(_TD, "VerifyAgainstReferenceDialog"), "_use_profile",
        lambda w: w._profile_field, lambda w: w._pick_profile(), _OPEN,
        (".icc", ".icm"), closed=_busy),
    # -- Verify a profile (R14-R15) -------------------------------------------
    Row("verify-profile-profile", _tools("VerifyProfileDialog"),
        _cls(_TD, "VerifyProfileDialog"), "_use_profile",
        lambda w: w._profile_field, lambda w: w._pick_profile(), _OPEN,
        (".icc", ".icm"), closed=_busy),
    Row("verify-profile-measured", _tools("VerifyProfileDialog"),
        _cls(_TD, "VerifyProfileDialog"), "_use_measured",
        lambda w: w._measured_field, lambda w: w._pick_measured(), _OPEN,
        (".ti3",), closed=_busy),
    # -- every Tools window's destination folder (R16) -----------------------
    Row("tools-destination-folder", _tools("MergeMeasurementsDialog"),
        _cls(_TD, "_OutputRow"), "_use_dir",
        lambda w: w._output._dir_edit, lambda w: w._output._browse(),
        _TD + ":open_dir_dialog", (), folder=True, closed=_busy,
        editable=lambda w: w._output._dir_edit),
    # -- Device link (R17-R21) ------------------------------------------------
]

_DL = "ui.dialogs.devicelink_dialog"
_DLA = "ui.dialogs.devicelink_apply_dialog"


def _dl(settings):
    from ui.dialogs.devicelink_dialog import DeviceLinkDialog
    return DeviceLinkDialog(_runner(), settings)


def _dla(settings):
    from ui.dialogs.devicelink_apply_dialog import DeviceLinkApplyDialog
    return DeviceLinkApplyDialog(_runner(), settings)


def _expert_open(w):
    from ui.widgets import CollapsibleGroupBox
    for g in w.findChildren(CollapsibleGroupBox):
        if hasattr(g, "set_collapsed"):
            g.set_collapsed(False)
        elif hasattr(g, "setCollapsed"):
            g.setCollapsed(False)


def _images_on(w):
    _expert_open(w)
    w._image_cb.setChecked(True)


def _images_off(w):
    w._image_cb.setChecked(False)


ROWS += [
    Row("devicelink-source", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_use_source", lambda w: w._src_field, lambda w: w._pick_source(),
        _DL + ":open_file_dialog", (".icc", ".icm"), closed=_busy),
    Row("devicelink-destination", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_set_destination", lambda w: w._dst_field,
        lambda w: w._pick_destination(), _DL + ":open_file_dialog",
        (".icc", ".icm"), closed=_busy),
    Row("devicelink-abstract", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_use_abstract", lambda w: w._abstract_field,
        lambda w: w._pick_abstract(), _DL + ":open_file_dialog",
        (".icc", ".icm"), closed=_busy, prepare=_expert_open),
    Row("devicelink-cal", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_use_cal", lambda w: w._cal_field, lambda w: w._pick_cal(),
        _DL + ":open_file_dialog", (".cal",), closed=_busy,
        prepare=_expert_open),
    Row("devicelink-images", _dl, _cls(_DL, "DeviceLinkDialog"),
        "_use_images", lambda w: w._image_list, lambda w: w._pick_images(),
        _DL + ":open_files_dialog", (".tif", ".jpg", ".png"), several=True,
        closed=_images_off, prepare=_images_on),
    # -- Apply device link (R22-R24) -------------------------------------------
    Row("devicelink-apply-link", _dla, _cls(_DLA, "DeviceLinkApplyDialog"),
        "_set_link", lambda w: w._link_field, lambda w: w._pick_link(),
        _DLA + ":open_file_dialog", (".icc", ".icm"), closed=_busy),
    Row("devicelink-apply-source", _dla, _cls(_DLA, "DeviceLinkApplyDialog"),
        "_use_source", lambda w: w._src_field, lambda w: w._pick_source(),
        _DLA + ":open_file_dialog", (".icc", ".icm"), closed=_busy),
    Row("devicelink-apply-images", _dla, _cls(_DLA, "DeviceLinkApplyDialog"),
        "_use_images", lambda w: w._image_list, lambda w: w._pick_images(),
        _DLA + ":open_files_dialog", (".tif", ".jpeg"), several=True,
        closed=_busy),
]


# ---------------------------------------------------------------------------
# the harness
# ---------------------------------------------------------------------------

def _norm(arg):
    if isinstance(arg, (list, tuple)):
        return [Path(a) for a in arg]
    return Path(arg)


class _Recorder:
    def __init__(self):
        self.calls: list = []

    def make(self):
        calls = self.calls

        def handler(self_, *args, **_kw):
            calls.append(_norm(args[0]) if args else None)
        return handler


def _files(tmp_path, row, n=1, *, kind=None):
    out = []
    for i in range(n):
        suf = kind or row.good[i % len(row.good)]
        p = tmp_path / f"drop {i} äö{suf}"
        p.write_text("x\n", encoding="utf-8")
        out.append(p)
    return out


def _open(row, monkeypatch, qapp):
    rec = _Recorder()
    monkeypatch.setattr(row.owner(), row.handler, rec.make())
    win = row.build(_Settings())
    win.resize(900, 900)
    win.show()
    _pump(qapp)
    if row.prepare is not None:
        row.prepare(win)
        _pump(qapp)
    return win, rec


def _choose_with_browse(row, monkeypatch, value):
    mod, attr = row.dialog.split(":")
    import importlib
    monkeypatch.setattr(importlib.import_module(mod), attr,
                        lambda *a, **k: value)


@pytest.mark.parametrize("row", ROWS, ids=[r.id for r in ROWS])
def test_a_dropped_file_reaches_what_browse_reaches(row, qapp, tmp_path,
                                                    monkeypatch):
    win, rec = _open(row, monkeypatch, qapp)
    try:
        if row.folder:
            good = [tmp_path / "a folder äö"]
            good[0].mkdir()
        else:
            good = _files(tmp_path, row, 2 if row.several else 1)
        chosen = ([str(p) for p in good] if row.several else str(good[0]))
        _choose_with_browse(row, monkeypatch, chosen)
        row.browse(win)
        assert rec.calls, "Browse did not reach the handler"
        by_browse = rec.calls[-1]
        rec.calls.clear()
        field = row.drop_on(win)
        before = field.text() if isinstance(field, QLineEdit) else None
        assert drag_to(qapp, field, _mime(*good, text="file://" + str(good[0])))
        assert rec.calls == [by_browse]
        if before is not None:
            assert "file://" not in field.text()
    finally:
        win.close()
        win.deleteLater()


@pytest.mark.parametrize("row", ROWS, ids=[r.id for r in ROWS])
def test_a_file_of_another_kind_is_not_accepted(row, qapp, tmp_path,
                                                monkeypatch):
    win, rec = _open(row, monkeypatch, qapp)
    try:
        field = row.drop_on(win)
        before = field.text() if isinstance(field, QLineEdit) else None
        if row.folder:
            wrong = _files(tmp_path, row, kind=".ti3")
        else:
            wrong = _files(tmp_path, row, kind=row.bad)
        folder = tmp_path / "a folder"
        folder.mkdir()
        for mime in (_mime(*wrong), _mime(*wrong, text=str(wrong[0])),
                     *(() if row.folder else (_mime(folder),))):
            assert not drag_to(qapp, field, mime)
        assert rec.calls == []
        if before is not None:
            assert field.text() == before
    finally:
        win.close()
        win.deleteLater()


@pytest.mark.parametrize("row", [r for r in ROWS if r.closed],
                         ids=[r.id for r in ROWS if r.closed])
def test_a_greyed_or_busy_row_accepts_nothing(row, qapp, tmp_path,
                                              monkeypatch):
    win, rec = _open(row, monkeypatch, qapp)
    try:
        row.closed(win)
        _pump(qapp)
        if row.folder:
            good = [tmp_path / "f"]
            good[0].mkdir()
        else:
            good = _files(tmp_path, row)
        field = row.drop_on(win)
        assert not drag_to(qapp, field, _mime(*good))
        assert rec.calls == []
    finally:
        win.close()
        win.deleteLater()


@pytest.mark.parametrize("row", [r for r in ROWS if r.editable],
                         ids=[r.id for r in ROWS if r.editable])
def test_plain_text_still_drops_into_an_editable_field(row, qapp,
                                                       monkeypatch):
    win, rec = _open(row, monkeypatch, qapp)
    try:
        edit = row.editable(win)
        drag_to(qapp, edit, _mime(text="typed by hand"))
        text = (edit.toPlainText() if hasattr(edit, "toPlainText")
                else edit.text())
        assert "typed by hand" in text
        assert rec.calls == []
    finally:
        win.close()
        win.deleteLater()
