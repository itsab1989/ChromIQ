# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Lines for the app log in one stable shape (4.3.50, A1-A8).

The app log is the ONE file a tester is asked to send (the project owner, 19 Nov
2026), so the events of a measurement are written there in a shape we can grep:
a short tag, a colon, then ``key=value`` pairs, English only, no translated
text. ``line("strip", id="A", attempt=2, result="kept")`` writes
``strip: id=A attempt=2 result=kept``.

EVERY FUNCTION HERE SWALLOWS ITS OWN FAULTS: a log line never raises into a
measurement. Values are shown short: a bool as on/off, a float with up to three
decimals, text with spaces as one token in quotes, a list by its length when it
is long. The privacy filter (``core.log_privacy``) still scrubs every line at the
handler.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("chromiq.events")

#: how long one value may be before it is cut
MAX_VALUE = 400
#: how long one line may be before it is cut (a rotation must not be eaten by one line)
MAX_LINE = 1200


def value(v) -> str:
    """One value as the log writes it."""
    try:
        if v is None:
            return "-"
        if isinstance(v, bool):
            return "on" if v else "off"
        if isinstance(v, float):
            return f"{v:.3f}".rstrip("0").rstrip(".") if v == v else "nan"
        if isinstance(v, (list, tuple, set, frozenset)):
            items = list(v)
            if len(items) <= 6 and all(isinstance(i, (str, int, float, bool)) or i is None
                                       for i in items):
                return "[" + ",".join(value(i) for i in items) + "]"
            return f"[{len(items)} items]"
        if isinstance(v, dict):
            return "{" + f"{len(v)} keys" + "}"
        text = str(v).replace("\n", " ").replace("\r", " ")
        if len(text) > MAX_VALUE:
            text = text[:MAX_VALUE] + "..."
        if not text:
            return "''"
        if any(c in text for c in " =\t"):
            return '"' + text.replace('"', "'") + '"'
        return text
    except Exception:      # noqa: BLE001
        return "?"


def pairs(**kv) -> str:
    """``key=value`` pairs in the order given."""
    out = []
    for k, v in kv.items():
        try:
            out.append(f"{k}={value(v)}")
        except Exception:      # noqa: BLE001
            out.append(f"{k}=?")
    return " ".join(out)


def flat(detail, prefix: str = "", depth: int = 2) -> "dict":
    """A detail dict flattened for :func:`pairs`: nested dicts to *depth* as
    ``a.b``, everything else shown by :func:`value` (long lists by their length)."""
    out: dict = {}
    try:
        for k, v in (detail or {}).items():
            key = f"{prefix}{k}"
            if isinstance(v, dict) and depth > 1:
                out.update(flat(v, key + ".", depth - 1))
            else:
                out[key] = v
    except Exception:      # noqa: BLE001
        pass
    return out


def line(tag: str, _level: int = logging.INFO, **kv) -> None:
    """Write ``<tag>: key=value ...``. Never raises."""
    try:
        text = f"{tag}: {pairs(**kv)}" if kv else f"{tag}:"
        if len(text) > MAX_LINE:
            text = text[:MAX_LINE] + " ...(cut)"
        log.log(_level, "%s", text)
    except Exception:      # noqa: BLE001
        pass


def text_line(tag: str, text: str, _level: int = logging.INFO, **kv) -> None:
    """``<tag>: key=value ... text="<text>"``: a free sentence after the pairs
    (for an on-screen line that has no message id). Never raises."""
    try:
        t = str(text).replace("\n", " | ").strip()
        if len(t) > MAX_LINE:
            t = t[:MAX_LINE] + "...(cut)"
        kv = {k: v for k, v in kv.items() if v is not None}
        head = f"{tag}: {pairs(**kv)}" if kv else f"{tag}:"
        log.log(_level, "%s text=%s", head, t)
    except Exception:      # noqa: BLE001
        pass


class Clock:
    """Seconds since a start, for ``took_s`` (monotonic; never raises)."""

    def __init__(self) -> None:
        self.t0 = time.monotonic()

    def s(self) -> float:
        try:
            return round(time.monotonic() - self.t0, 1)
        except Exception:      # noqa: BLE001
            return -1.0
