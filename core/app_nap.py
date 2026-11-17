# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Keep macOS's App Nap away while one time-critical thing runs (round B of the i1iO table drive,
NEXT_STEPS step 10: "App Nap").

A strip row on the i1iO table has ONE path from the scan move to the lamp trigger, and the
table's answer to the move is read in a tight loop of short waits. App Nap may slow the timers of
an app that is not in front (the person may click into another window while a row runs), so the
table job holds this around every strip move: ``NSProcessInfo.beginActivityWithOptions_reason_``
with "user initiated" and "latency critical", ended right after the row. On every other system,
or when pyobjc is missing, it does nothing. It never raises."""
from __future__ import annotations

import sys

#: NSActivityUserInitiated | NSActivityLatencyCritical (Foundation, NSProcessInfo.h)
_OPTIONS = 0x00FFFFFF | 0xFF00000000


class latency_critical:
    """A context manager: macOS's "latency critical" activity while it is held."""

    def __init__(self, reason: str = "ChromIQ reads a row with the i1iO table") -> None:
        self.reason = reason
        self._token = None
        self.active = False

    def __enter__(self):
        if sys.platform == "darwin":
            try:
                from Foundation import NSProcessInfo
                self._token = NSProcessInfo.processInfo().beginActivityWithOptions_reason_(
                    _OPTIONS, self.reason)
                self.active = self._token is not None
            except Exception:      # noqa: BLE001 - never stops the measurement
                self._token = None
        return self

    def __exit__(self, *exc) -> bool:
        tok, self._token = self._token, None
        if tok is not None:
            try:
                from Foundation import NSProcessInfo
                NSProcessInfo.processInfo().endActivity_(tok)
            except Exception:      # noqa: BLE001
                pass
        self.active = False
        return False
