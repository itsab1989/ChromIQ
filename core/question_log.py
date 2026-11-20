# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Every question a window asks, with the answer given, in the app log (4.3.50, A4).

ONE central place instead of 170 call sites: the application's dialog-focus
filter (``ui.widgets.DialogFocusFilter``, already installed on every event) calls
:func:`window_shown` when a dialog window is shown and :func:`window_hidden`
when it goes, and this module writes one line::

    question: id=M-STRIP-PART-SLIPPED-LATE window=QDialog answer="Keep it" button=keep_btn
              result=accepted open_s=4.2

The id is the §M catalogue id of the message the window shows (every message is
rendered through ``workflow.measurement_messages.Message.render``, which calls
:func:`note_rendered`), else the window's object name, else its English title.
The answer is the English text of the button pressed (translated labels are
looked up backwards in the active catalogue), its object name, and the dialog's
result. A window closed without a button says ``answer=closed``.

Answers given without a window (the table's unguided mode, which carries on by
itself) are written by :func:`auto_answered`. Nothing here raises.
"""
from __future__ import annotations

import html
import re
import time
from collections import OrderedDict

from core.app_log import line

_RENDERED: "OrderedDict[str, tuple[str, str, float]]" = OrderedDict()
_MAX = 64
_REVERSE: "dict[str, str] | None" = None
_REVERSE_FOR = None
_TAGS = re.compile(r"<[^>]+>")


def note_rendered(msg_id: str, title: str, body: str) -> None:
    """A catalogue message was rendered (it is about to be shown, or logged)."""
    try:
        _RENDERED[str(msg_id)] = (str(title), str(body)[:200], time.monotonic())
        _RENDERED.move_to_end(str(msg_id))
        while len(_RENDERED) > _MAX:
            _RENDERED.popitem(last=False)
    except Exception:      # noqa: BLE001
        pass


def english(text: str) -> str:
    """The English source of a translated UI text (the catalogue backwards);
    the text itself when it is English or unknown."""
    global _REVERSE, _REVERSE_FOR
    try:
        t = str(text or "").replace("&&", "\x00").replace("&", "").replace("\x00", "&")
        from core import i18n
        cat = getattr(i18n, "_catalog", None) or {}
        if not cat:
            return t
        if _REVERSE is None or _REVERSE_FOR is not cat or len(_REVERSE) != len(cat):
            _REVERSE = {}
            for k, v in cat.items():
                if isinstance(v, str):
                    _REVERSE.setdefault(v.replace("&", ""), k)
            _REVERSE_FOR = cat
        return _REVERSE.get(t, t)
    except Exception:      # noqa: BLE001
        return str(text or "")


def _plain(s: str) -> str:
    return html.unescape(_TAGS.sub(" ", str(s or ""))).replace(" ", " ")


def _texts_of(win) -> "list[str]":
    out = []
    try:
        out.append(win.windowTitle())
        if hasattr(win, "text") and callable(win.text):
            out.append(win.text())
        from PyQt6.QtWidgets import QLabel
        for lab in win.findChildren(QLabel)[:12]:
            out.append(lab.text())
    except Exception:      # noqa: BLE001
        pass
    return [_plain(t) for t in out if t]


def message_id_of(win) -> str:
    """The catalogue id whose title (or the start of whose body) the window
    shows, newest first; else ""."""
    try:
        texts = _texts_of(win)
        joined = "\n".join(texts)
        for mid, (title, body, _t) in reversed(list(_RENDERED.items())):
            pt, pb = _plain(title).strip(), _plain(body).strip()[:60]
            if (pt and pt in joined) or (pb and pb in joined):
                return mid
    except Exception:      # noqa: BLE001
        pass
    return ""


def _is_question_window(win) -> bool:
    try:
        from PyQt6.QtWidgets import QDialog, QFileDialog, QProgressDialog
        if not isinstance(win, QDialog) or isinstance(win, (QFileDialog, QProgressDialog)):
            return False
        if getattr(win, "_cq_question_skip", False):
            return False
        return True
    except Exception:      # noqa: BLE001
        return False


def window_shown(win) -> None:
    """Called by the dialog filter on a dialog window's Show. Never raises."""
    try:
        if not _is_question_window(win):
            return
        if getattr(win, "_cq_question_t0", None) is not None:
            return
        win._cq_question_t0 = time.monotonic()
        win._cq_question_id = message_id_of(win)
        rec = _recorder_class()(win)
        win._cq_question_clicks = rec
        from PyQt6.QtWidgets import QAbstractButton
        for b in win.findChildren(QAbstractButton):
            try:
                # pressed, not clicked: a button whose clicked is connected
                # to accept() first hides the window before a later clicked
                # slot runs; pressed comes before clicked (click(), Return,
                # Space and the mouse alike)
                b.pressed.connect(rec.clicked)
            except Exception:      # noqa: BLE001
                pass
    except Exception:      # noqa: BLE001
        pass


def window_hidden(win) -> None:
    """Called by the dialog filter on a dialog window's Hide. Never raises."""
    try:
        t0 = getattr(win, "_cq_question_t0", None)
        if t0 is None:
            return
        win._cq_question_t0 = None
        mid = getattr(win, "_cq_question_id", "") or message_id_of(win)
        btn = None
        try:
            cb = getattr(win, "clickedButton", None)
            btn = cb() if callable(cb) else None
        except Exception:      # noqa: BLE001
            btn = None
        rec = getattr(win, "_cq_question_clicks", None)
        if btn is None and rec is not None:
            btn = rec.last
        answer, name = "closed", None
        if btn is not None:
            try:
                answer = english(btn.text()) or "(no text)"
                name = btn.objectName() or None
            except Exception:      # noqa: BLE001
                pass
        try:
            res = win.result()
            result = {1: "accepted", 0: "rejected"}.get(int(res), str(int(res)))
        except Exception:      # noqa: BLE001
            result = None
        title = (english(win.windowTitle()) or None) if not mid else None
        line("question", id=mid or win.objectName() or None,
             window=type(win).__name__, title=title, answer=answer, button=name,
             result=result, open_s=round(time.monotonic() - t0, 1))
    except Exception:      # noqa: BLE001
        pass


def _recorder_class():
    """A QObject child of the window that remembers the last button pressed
    (``sender()``, a bound slot: CLAUDE.md, never a self-capturing lambda)."""
    global _RECORDER
    if _RECORDER is None:
        from PyQt6.QtCore import QObject, pyqtSlot

        class ClickRecorder(QObject):
            def __init__(self, parent=None) -> None:
                super().__init__(parent)
                self.last = None

            @pyqtSlot()
            def clicked(self) -> None:
                try:
                    self.last = self.sender() or self.last
                except Exception:      # noqa: BLE001
                    pass
        _RECORDER = ClickRecorder
    return _RECORDER


_RECORDER = None


def answered(question_id: str, answer: str, **kv) -> None:
    """A question answered where the code knows the answer by name (a window
    whose buttons hand back a word, e.g. the misaligned strip's "keep")."""
    line("question answer", id=question_id, answer=answer, **kv)


def auto_answered(question_id: str, answer: str, **kv) -> None:
    """A question nobody saw: answered by ChromIQ itself (the table's unguided
    mode, a "don't ask again"), so the log says it was automatic."""
    line("question answer", id=question_id, answer=answer, by="automatic", **kv)
