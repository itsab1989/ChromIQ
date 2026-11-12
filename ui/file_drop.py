"""Files dropped from the platform's file manager (4.3.32,
jctay, forum post 150152: "would it be possible to add drag-and-drop for
selecting files?"; 4.3.33: every Browse row where that is safe, the owner:
"in the other places where safe and beneficial").

Until this module the app accepted no file drops at all (the only drop in it
is the patch set editor's internal reorder), so there was no pattern to
follow; this is the one. Three parts:

* :func:`paths_from_mime` turns what the file manager hands over into local
  paths: only ``file:`` URLs (decoded: spaces, umlauts; ``file:///C:/...``
  is ``C:/...`` on every platform), only regular files, only the listed
  suffixes in any case. A folder, a web link or a file of another kind is
  left out, by name and with its reason, so the window can say so. With
  ``folders=True`` it is the other way round: folders only (a folder row).
* :class:`FileDropZone` is a plain container around a row of controls.
* :class:`FileDropTarget` gives an EXISTING widget (a group box, a row
  widget, a list) the same behaviour, through an event filter, so a row that
  already has its own container is not rebuilt.

Both work the same way. While a drag that holds a usable file is over the
row, an overlay draws a frame and a light wash in the window's accent (in
Neutral the one ACTION ink, as every accent there); the controls under it
are not re-laid out or re-styled. A drop hands the files on through
``files_dropped`` (and, for a row that takes one file or one folder,
``file_dropped``) on the next turn of the event loop, never inside the drop
itself: on macOS a drop is delivered inside the system's drag session, and
loading there would hold the file manager's drag animation until the load
is done.

THE ROW DECIDES, NOT THE FIELD IN IT. An editable text field accepts any
drag that carries text, and a file manager's drag can carry the file's URL
as text too, so until 4.3.33 a file dropped on an editable path field could
paste ``file:///...`` into it. Every text field inside a row (and any widget
named with :meth:`take_file_drags_from`) passes a drag that holds a local
file on to the row: the row either takes the file as Browse would, or
refuses it. A drag of plain text, or of a web link, still reaches the field
as before.

A row whose *guard* says no (its Browse button is greyed, its window is busy)
accepts nothing, and Qt itself sends no drag to a disabled or hidden widget.

Handlers are overrides and the delivery is a bound method (CLAUDE.md: no
self-capturing lambdas on signals).
"""
from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtCore import (QEvent, QMimeData, QObject, QRectF, Qt, QTimer,
                          QUrl, pyqtSignal)
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (QAbstractScrollArea, QLineEdit, QWidget)


_DRIVE = re.compile(r"^/[A-Za-z]:[/\\]")


# How far the frame reaches outside the row (the window has 22 px side
# margins and 12 px between rows, so it stays clear of its neighbours).
_OUTSET = 6

_DRAG_EVENTS = (QEvent.Type.DragEnter, QEvent.Type.DragMove,
                QEvent.Type.DragLeave, QEvent.Type.Drop)


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


def holds_local_files(mime: "QMimeData | None") -> bool:
    """Whether a drag carries at least one ``file:`` URL (whatever its kind):
    such a drag belongs to the row, not to a text field in it."""
    if mime is None or not mime.hasUrls():
        return False
    return any(_local_path(u) is not None for u in mime.urls())


def paths_from_mime(mime: "QMimeData | None", suffixes,
                    *, check_disk: bool = True, folders: bool = False
                    ) -> "tuple[list[Path], list[tuple[str, str]]]":
    """(usable files in the order dropped, what was left out and why).

    Left out: ``(name, reason)`` with reason ``"folder"``, ``"kind"`` (a
    file of another kind), ``"file"`` (a file where a folder is wanted) or
    ``"missing"`` (no such file here, or a link that is not a local file).
    *suffixes* are compared without regard to case (``.TI3`` is a
    ``.ti3``). With *folders* only folders are usable and *suffixes* are not
    asked. Without *check_disk* the disk is not asked, so a path from
    another computer can be parsed in a test."""
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
        if folders:
            try:
                is_dir, exists = p.is_dir(), p.exists()
            except OSError:
                is_dir = exists = False
            if not check_disk:
                is_dir = exists = True
            if is_dir:
                got.append(p)
            elif exists:
                left_out.append((name, "file"))
            else:
                left_out.append((name, "missing"))
            continue
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


def guard_allows(guard) -> bool:
    """*guard* is None (always), a widget (while it is enabled: the row's
    Browse button), a callable (its answer), or a tuple of these (all of
    them)."""
    if guard is None:
        return True
    if isinstance(guard, (tuple, list)):
        return all(guard_allows(g) for g in guard)
    try:
        if isinstance(guard, QWidget):
            return guard.isEnabled()
        return bool(guard())
    except RuntimeError:              # the guard's widget is gone
        return False


def drop_hint(kind: str = "file") -> str:
    """The one sentence a row's existing help gains (4.3.33): *kind* is
    ``"file"`` (a row that takes one file), ``"files"`` (a list that takes
    several) or ``"folder"`` (a folder row). The file manager is named as
    each platform calls it (#130)."""
    from core.i18n import tr
    from core.platform_paths import file_manager_name
    if kind == "folder":
        text = tr(
            "You can also drag a folder from {manager} and drop it on this "
            "row, and ChromIQ uses it just as if you had chosen it with the "
            "browse button.")
    elif kind == "files":
        text = tr(
            "You can also drag one or several files from {manager} and drop "
            "them on this list, and ChromIQ adds them just as the add button "
            "does. Files of other kinds are left out.")
    else:
        text = tr(
            "You can also drag a file from {manager} and drop it on this row, "
            "and ChromIQ uses it just as if you had chosen it with the browse "
            "button. A file of another kind is not accepted.")
    return text.format(manager=file_manager_name())


def with_drop_hint(text: str, kind: str = "file") -> str:
    """*text* (a row's existing help) with :func:`drop_hint` after it."""
    return (text.rstrip() + "\n\n" + drop_hint(kind)) if text else text


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


class _Drops(QObject):
    """What a drop row knows and does, shared by :class:`FileDropZone` (the
    row is the zone) and :class:`FileDropTarget` (the row is a widget that
    already existed)."""

    files_dropped = pyqtSignal(list, list)
    file_dropped = pyqtSignal(object)

    def __init__(self, row: QWidget, suffixes, *, single: bool,
                 folders: bool, guard, colour: "str | None",
                 accent: "str | None", declutter) -> None:
        super().__init__(row)
        self._row = row
        self._suffixes = suffixes
        self._single = single or folders
        self._folders = folders
        self._guard = guard
        self._declutter = declutter
        self._pending: list[Path] = []
        self._pending_left: list[tuple[str, str]] = []
        self._lit = False
        self._accent = accent
        self._watched: set[int] = set()
        row.setAcceptDrops(True)
        # The frame sits a few pixels OUTSIDE the row, on the window, so it
        # does not run through the row's first letter (measured on screen,
        # 2026-11-12: drawn inside the row it cut the "M" of "Measurement:").
        host = row.parentWidget() or row
        self._overlay = _DropOverlay(host)
        self._overlay.colour = colour or accent or "#37bcd6"
        self._fixed_colour = colour is not None

    # --- what is taken -----------------------------------------------
    def suffixes(self) -> tuple:
        s = self._suffixes
        if callable(s):
            s = s()
        return tuple(s or ())

    def open_now(self) -> bool:
        """The guard: False while the row's Browse would not run."""
        return guard_allows(self._guard)

    def sort(self, mime):
        if not self.open_now():
            return [], []
        files, left = paths_from_mime(mime, self.suffixes(),
                                      folders=self._folders)
        if self._single and len(files) != 1:
            return [], left
        return files, left

    def usable(self, mime) -> "list[Path]":
        return self.sort(mime)[0]

    # --- appearance --------------------------------------------------
    def set_colour(self, colour: str) -> None:
        self._overlay.colour = colour
        self._fixed_colour = True
        self._overlay.update()

    def show_highlight(self, on: bool) -> None:
        self._lit = on
        if on:
            if not self._fixed_colour and self._accent:
                from ui.theme import accent_for
                self._overlay.colour = accent_for(self._accent)
            self.place_overlay()
            self._overlay.raise_()
            self._overlay.show()
        else:
            self._overlay.hide()

    def place_overlay(self) -> None:
        host = self._overlay.parentWidget()
        if host is self._row:
            self._overlay.setGeometry(self._row.rect())
            return
        top_left = self._row.mapTo(host, self._row.rect().topLeft())
        r = self._row.rect().translated(top_left)
        self._overlay.setGeometry(
            r.adjusted(-_OUTSET, -_OUTSET, _OUTSET, _OUTSET)
            .intersected(host.rect()))

    # --- the fields inside the row -----------------------------------
    def watch(self, widget: QWidget) -> None:
        """A drag holding a local file that reaches *widget* is passed on to
        the row (Qt hands an ignored drag to the parent); plain text and web
        links still reach the widget."""
        targets = [widget]
        if isinstance(widget, QAbstractScrollArea):
            targets.append(widget.viewport())
        for w in targets:
            if id(w) in self._watched:
                continue
            self._watched.add(id(w))
            w.installEventFilter(self)

    def watch_fields(self) -> None:
        for edit in self._row.findChildren(QLineEdit):
            self.watch(edit)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 — Qt's name
        if (event.type() in _DRAG_EVENTS
                and event.type() != QEvent.Type.DragLeave
                and holds_local_files(event.mimeData())):
            event.ignore()
            return True
        return False

    # --- the drag ----------------------------------------------------
    def take(self, event) -> bool:
        if self.usable(event.mimeData()):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return True
        event.ignore()
        return False

    def enter(self, event) -> None:
        self.watch_fields()
        self.show_highlight(self.take(event))

    def move(self, event) -> None:
        self.show_highlight(self.take(event))

    def leave(self, event) -> None:
        self.show_highlight(False)
        event.accept()

    def drop(self, event) -> None:
        self.show_highlight(False)
        files, left = self.sort(event.mimeData())
        if not files:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self._pending, self._pending_left = files, left
        QTimer.singleShot(0, self.deliver)

    def deliver(self) -> None:
        files, self._pending = self._pending, []
        left, self._pending_left = self._pending_left, []
        # Busy or greyed since the drop: nothing happens, as a press on the
        # greyed Browse button would do nothing.
        if not files or not self.open_now():
            return
        if self._declutter is not None:
            # As the row's Browse does (`open_file_dialog(declutter_settings=
            # ...)`): a legacy flat project folder is tidied before the file
            # is used.
            try:
                from core.file_manager import maybe_declutter_on_load
                maybe_declutter_on_load(str(files[0]), self._declutter)
            except Exception:      # noqa: BLE001 — as Browse: never fatal
                pass
        self.files_dropped.emit(files, left)
        if self._single and len(files) == 1:
            self.file_dropped.emit(files[0])


class FileDropZone(QWidget):
    """A container that accepts files of *suffixes* dropped on it.

    *single*: accept a drag only when it holds exactly one usable file (a
    field that shows one file). Otherwise any drag with at least one usable
    file is accepted, and the drop hands on the usable ones only. *folders*:
    a folder row, exactly one folder. *suffixes* may be a callable, for a
    row whose Browse filter changes (it is asked at every drag). *guard*: a
    widget (its Browse button: the row takes drops while it is enabled) or
    a callable answering whether the row takes drops now. *accent*: the
    window's accent, resolved for the appearance at each drag; *colour*
    fixes the colour instead. *declutter*: the AppSettings the row's Browse
    hands to ``open_file_dialog(declutter_settings=...)``."""

    def __init__(self, parent: QWidget, suffixes=(), *, single: bool = False,
                 folders: bool = False, guard=None,
                 colour: "str | None" = None, accent: "str | None" = None,
                 declutter=None) -> None:
        super().__init__(parent)
        if colour is None and accent is None:
            colour = "#37bcd6"
        self._drops = _Drops(self, suffixes, single=single, folders=folders,
                             guard=guard, colour=colour, accent=accent,
                             declutter=declutter)
        self.files_dropped = self._drops.files_dropped
        self.file_dropped = self._drops.file_dropped
        self._overlay = self._drops._overlay

    @classmethod
    def around(cls, row_layout, parent: QWidget, suffixes=(), *,
               spacing: "int | None" = None, **kw) -> "FileDropZone":
        """A zone holding *row_layout* (a layout not yet added anywhere), to
        add to the window's layout in its place: no margins, and the spacing
        it would have had there."""
        zone = cls(parent, suffixes, **kw)
        if spacing is not None and row_layout.spacing() < 0:
            row_layout.setSpacing(spacing)
        zone.setLayout(row_layout)
        row_layout.setContentsMargins(0, 0, 0, 0)
        zone._drops.watch_fields()
        return zone

    # --- appearance --------------------------------------------------
    def set_highlight_colour(self, colour: str) -> None:
        self._drops.set_colour(colour)

    def is_highlighted(self) -> bool:
        return self._drops._lit

    def take_file_drags_from(self, *widgets: QWidget) -> None:
        for w in widgets:
            self._drops.watch(w)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # The fields are in the row by now (a zone is often made first and
        # filled after).
        self._drops.watch_fields()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._drops._lit:
            self._drops.place_overlay()

    # --- the drag ----------------------------------------------------
    def usable(self, mime: "QMimeData | None") -> "list[Path]":
        return self._drops.usable(mime)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        self._drops.enter(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        self._drops.move(event)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._drops.leave(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._drops.drop(event)


class FileDropTarget(_Drops):
    """:class:`FileDropZone`'s behaviour on a widget that already exists (a
    group box, a row widget, a list), through an event filter on it. Same
    arguments. Kept alive by its widget (a QObject child)."""

    def __init__(self, widget: QWidget, suffixes=(), *, single: bool = False,
                 folders: bool = False, guard=None,
                 colour: "str | None" = None, accent: "str | None" = None,
                 declutter=None) -> None:
        if colour is None and accent is None:
            colour = "#37bcd6"
        super().__init__(widget, suffixes, single=single, folders=folders,
                         guard=guard, colour=colour, accent=accent,
                         declutter=declutter)
        self._own = widget
        targets = [widget]
        if isinstance(widget, QAbstractScrollArea):
            # A list or a text box takes its drags on its viewport.
            widget.viewport().setAcceptDrops(True)
            targets.append(widget.viewport())
        self._own_ids = {id(t) for t in targets}
        for t in targets:
            self._watched.add(id(t))
            t.installEventFilter(self)
        self.watch_fields()

    def set_highlight_colour(self, colour: str) -> None:
        self.set_colour(colour)

    def is_highlighted(self) -> bool:
        return self._lit

    def take_file_drags_from(self, *widgets: QWidget) -> None:
        for w in widgets:
            self.watch(w)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 — Qt's name
        t = event.type()
        if t not in _DRAG_EVENTS and t not in (QEvent.Type.Resize,
                                               QEvent.Type.Show):
            return False
        # By id: a widget being destroyed still sends events through here,
        # and asking it anything then raises.
        if id(obj) not in self._own_ids:
            return super().eventFilter(obj, event)
        if t == QEvent.Type.Resize and self._lit:
            self.place_overlay()
            return False
        if t == QEvent.Type.Show:
            self.watch_fields()
            return False
        if t not in _DRAG_EVENTS:
            return False
        if t == QEvent.Type.DragLeave:
            if not self._lit:
                return False
            self.leave(event)
            return True
        if not holds_local_files(event.mimeData()):
            # Plain text or a web link: the widget's own handling, as before.
            return False
        if t == QEvent.Type.DragEnter:
            self.enter(event)
        elif t == QEvent.Type.DragMove:
            self.move(event)
        else:
            self.drop(event)
        return True
