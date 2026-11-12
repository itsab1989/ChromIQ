"""Files dropped from Finder, Explorer or a Linux file manager (4.3.32,
jctay, forum post 150152: "would it be possible to add drag-and-drop for
selecting files?").

Until this module the app accepted no file drops at all (the only drop in it
is the patch set editor's internal reorder), so there was no pattern to
follow; this is the one. Two parts:

* :func:`paths_from_mime` turns what the file manager hands over into local
  paths: only ``file:`` URLs (decoded: spaces, umlauts; ``file:///C:/...``
  is ``C:/...`` on every platform), only regular files, only the listed
  suffixes in any case. A folder, a web link or a file of another kind is
  left out, by name and with its reason, so the window can say so.
* :class:`FileDropZone` is a plain container around a row of controls. While
  a drag that holds at least one usable file is over it, an overlay draws a
  frame and a light wash in the window's accent (in Neutral the one ACTION
  ink, as every accent there); the controls under it are not re-laid out or
  re-styled. A drop hands the files on through :attr:`files_dropped` on the
  next turn of the event loop, never inside the drop itself: on macOS a drop
  is delivered inside the system's drag session, and loading there would
  hold the file manager's drag animation until the load is done.

Handlers are overrides and the delivery is a bound method (CLAUDE.md: no
self-capturing lambdas on signals).
"""
from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtCore import QMimeData, QRectF, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


_DRIVE = re.compile(r"^/[A-Za-z]:[/\\]")


# How far the frame reaches outside the row (the window has 22 px side
# margins and 12 px between rows, so it stays clear of its neighbours).
_OUTSET = 6


def _local_path(url: QUrl) -> "str | None":
    """The local path a ``file:`` URL names, or None for anything else.
    ``toLocalFile`` decodes ``%20`` and ``%C3%BC`` and keeps a UNC host
    (``file://server/share/a.ti3`` -> ``//server/share/a.ti3``), but strips
    the slash before a drive letter only on Windows (measured, Qt 6.11 on
    macOS: ``file:///C:/a.ti3`` -> ``/C:/a.ti3``), so that is done here, the
    same on every platform."""
    if not url.isValid() or not url.isLocalFile():
        return None
    text = url.toLocalFile()
    if _DRIVE.match(text):
        text = text[1:]
    return text or None


def paths_from_mime(mime: "QMimeData | None", suffixes,
                    *, check_disk: bool = True
                    ) -> "tuple[list[Path], list[tuple[str, str]]]":
    """(usable files in the order dropped, what was left out and why).

    Left out: ``(name, reason)`` with reason ``"folder"``, ``"kind"`` (a
    file of another kind) or ``"missing"`` (no such file here, or a link
    that is not a local file). *suffixes* are compared without regard to
    case (``.TI3`` is a ``.ti3``). Without *check_disk* the disk is not
    asked, so a path from another computer can be parsed in a test."""
    if mime is None or not mime.hasUrls():
        return [], []
    want = {s.lower() for s in suffixes}
    got: list[Path] = []
    left_out: list[tuple[str, str]] = []
    for url in mime.urls():
        text = _local_path(url)
        if text is None:
            left_out.append((url.toDisplayString(), "missing"))
            continue
        p = Path(text)
        name = p.name or text
        if check_disk:
            try:
                is_dir, is_file = p.is_dir(), p.is_file()
            except OSError:
                is_dir = is_file = False
            if is_dir:
                left_out.append((name, "folder"))
                continue
            if p.suffix.lower() not in want:
                left_out.append((name, "kind"))
                continue
            if not is_file:
                left_out.append((name, "missing"))
                continue
        elif p.suffix.lower() not in want:
            left_out.append((name, "kind"))
            continue
        got.append(p)
    return got, left_out


class _DropOverlay(QWidget):
    """The highlight, drawn ON TOP of the zone's controls, so a list or a
    field that paints its own background does not hide it. Transparent for
    the mouse; shown only while a usable drag hovers."""

    def __init__(self, parent: "QWidget | None") -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.colour = "#37bcd6"
        self.hide()

    def paintEvent(self, _event) -> None:  # noqa: N802 — Qt's name
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        edge = QColor(self.colour)
        wash = QColor(self.colour)
        wash.setAlphaF(0.12)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(wash)
        pen = QPen(edge, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(rect, 6, 6)
        p.end()


class FileDropZone(QWidget):
    """A container that accepts files of *suffixes* dropped on it.

    *single*: accept a drag only when it holds exactly one usable file (a
    field that shows one file). Otherwise any drag with at least one usable
    file is accepted, and the drop hands on the usable ones only."""

    # (usable files: list[Path], left out: list[(name, reason)])
    files_dropped = pyqtSignal(list, list)

    def __init__(self, parent: QWidget, suffixes, *, single: bool = False,
                 colour: str = "#37bcd6") -> None:
        super().__init__(parent)
        self._suffixes = tuple(suffixes)
        self._single = single
        self._pending: list[Path] = []
        self._pending_left: list[tuple[str, str]] = []
        self._lit = False
        self.setAcceptDrops(True)
        # The frame sits a few pixels OUTSIDE the row, on the window, so it
        # does not run through the row's first letter (measured on screen,
        # 2026-11-12: drawn inside the row it cut the "M" of "Measurement:").
        self._overlay = _DropOverlay(parent)
        self._overlay.colour = colour

    # --- appearance --------------------------------------------------
    def set_highlight_colour(self, colour: str) -> None:
        self._overlay.colour = colour
        self._overlay.update()

    def is_highlighted(self) -> bool:
        return self._lit

    def _show_highlight(self, on: bool) -> None:
        self._lit = on
        if on:
            self._place_overlay()
            self._overlay.raise_()
            self._overlay.show()
        else:
            self._overlay.hide()

    def _place_overlay(self) -> None:
        host = self._overlay.parentWidget()
        top_left = self.mapTo(host, self.rect().topLeft())
        r = self.rect().translated(top_left)
        self._overlay.setGeometry(
            r.adjusted(-_OUTSET, -_OUTSET, _OUTSET, _OUTSET)
            .intersected(host.rect()))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._lit:
            self._place_overlay()

    # --- the drag ----------------------------------------------------
    def usable(self, mime: "QMimeData | None") -> "list[Path]":
        return self._sort(mime)[0]

    def _sort(self, mime):
        files, left = paths_from_mime(mime, self._suffixes)
        if self._single and len(files) != 1:
            return [], left
        return files, left

    def _take(self, event) -> bool:
        if self.usable(event.mimeData()):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return True
        event.ignore()
        return False

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        self._show_highlight(self._take(event))

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        self._show_highlight(self._take(event))

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._show_highlight(False)
        event.accept()

    def dropEvent(self, event) -> None:  # noqa: N802
        self._show_highlight(False)
        files, left = self._sort(event.mimeData())
        if not files:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self._pending, self._pending_left = files, left
        QTimer.singleShot(0, self._deliver)

    def _deliver(self) -> None:
        files, self._pending = self._pending, []
        left, self._pending_left = self._pending_left, []
        if files:
            self.files_dropped.emit(files, left)
