"""Every change of a colour setting says in the app log who made it
(issue 217, 2026-11-21).

A tester's profiles were built with the CIE 2015 2 degree observer and his
app log could not say whether he chose it, a preset brought it, or the run's
stored settings did. Testers are asked for the app log alone, so the log has
to carry it: old value, new value, and the source.

The source is named by the code that sets the controls, around the call
(`setting_source`); sources nest, and the log line joins them ("the target's
stored settings (run1) > nothing stored: the saved defaults"). A change with
no source named was made by the person in the control when Qt says so
(``activated``, which follows ``currentIndexChanged`` in the same call for
every pick by mouse, keyboard or wheel), and is logged as "set by the
program, no source named" otherwise, so a path nobody named still shows up.

The watcher is a QObject child of the control with bound-method slots, never
a closure (CLAUDE.md, the fade-scroll crash).
"""
from __future__ import annotations

from contextlib import contextmanager

from PyQt6.QtCore import QObject, QTimer

from core.logger import get_logger

log = get_logger(__name__)

#: the sources named around the code running now, outermost first
_SOURCES: "list[str]" = []

SOURCE_USER = "the user, in the control"
SOURCE_UNNAMED = "set by the program, no source named"


@contextmanager
def setting_source(source: str):
    """Name the source of every setting change made inside the block."""
    _SOURCES.append(str(source))
    try:
        yield
    finally:
        _SOURCES.pop()


def current_source() -> str:
    return " > ".join(_SOURCES)


def _value(v) -> str:
    return repr("" if v is None else v)


class _Watch(QObject):
    """Logs one control's changes. *read* gives its current value."""

    def __init__(self, widget, tab: str, name: str, kind: str) -> None:
        super().__init__(widget)
        self._w = widget
        self._tab = tab
        self._name = name
        self._kind = kind
        self._last = self._read()
        self._pending: "tuple | None" = None
        if kind == "combo":
            widget.currentIndexChanged.connect(self._on_changed)
            widget.activated.connect(self._on_user)
        else:
            widget.toggled.connect(self._on_changed)
            widget.clicked.connect(self._on_user)

    def _read(self):
        try:
            return (self._w.currentData() if self._kind == "combo"
                    else bool(self._w.isChecked()))
        except RuntimeError:      # the control is gone
            return None

    def _write(self, old, new, source: str) -> None:
        log.info("Setting changed: %s, %s: %s -> %s (source: %s)",
                 self._tab, self._name, _value(old), _value(new), source)

    def _on_changed(self, *_a) -> None:
        old, new = self._last, self._read()
        self._last = new
        if old == new:
            return
        src = current_source()
        if src:
            self._pending = None
            self._write(old, new, src)
            return
        # The person's own pick is told by `activated` / `clicked`, which Qt
        # emits right after this, in the same call. Anything else is logged
        # once the event loop turns.
        self._pending = (old, new)
        QTimer.singleShot(0, self._flush)

    def _on_user(self, *_a) -> None:
        if self._pending is not None:
            old, new = self._pending
            self._pending = None
            self._write(old, new, SOURCE_USER)

    def _flush(self) -> None:
        if self._pending is not None:
            old, new = self._pending
            self._pending = None
            self._write(old, new, SOURCE_UNNAMED)


def watch(widget, *, tab: str, name: str) -> None:
    """Log every change of *widget* (a combo box or a check box)."""
    if widget is None:
        return
    kind = "combo" if hasattr(widget, "currentIndexChanged") else "check"
    _Watch(widget, tab, name, kind)
