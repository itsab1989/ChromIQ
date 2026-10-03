"""Keep the C library's NUMBER locale at "C" on macOS.

Qt calls ``setlocale(LC_ALL, "")`` while a ``QApplication`` is constructed, so
on a German Mac the process runs with ``LC_NUMERIC=de_DE`` from then on. On
macOS 27.0 that, together with Qt's NATIVE message box (an ``NSAlert``),
aborts the process the moment a question is shown: SIGTRAP in CoreUI,
``targetSizeInPoints.width>0 && targetSizeInPoints.height>0``. Measured
2026-10-02 on macOS 27.0.1 / Qt 6.11: a plain ``QMessageBox`` crashed 5 of 5
under ``de_DE`` and 0 of 22 with ``LC_NUMERIC=C`` (G_challenge_misc and
E_popup_watchdog in that session's reports). Other projects hit the same
trigger: wxWidgets #26977, cmux #7880 (Apple FB24679653).

The shipped app escaped by luck: an app-wide stylesheet is always set
(``ui/theme.py``), and with one Qt never uses the native box. A driver or a
screenshot tool without the stylesheet did crash, and any future path that
shows a native box would too. So the number locale is pinned right after the
``QApplication`` exists, which is where Qt changed it.

Safe for the app: nothing in ChromIQ formats or parses numbers through the C
locale (Python's float formatting ignores it; text encoding reads LC_CTYPE,
which is left alone), and every number the user sees comes from ``QLocale``.
"""
from __future__ import annotations

import locale
import sys

from core.logger import get_logger

log = get_logger(__name__)


def pin_c_numeric_locale() -> bool:
    """Set ``LC_NUMERIC`` to "C" on macOS. Call it right AFTER constructing
    the ``QApplication``. Returns True when it changed something."""
    if sys.platform != "darwin":
        return False
    try:
        before = locale.setlocale(locale.LC_NUMERIC)
        if before == "C":
            return False
        locale.setlocale(locale.LC_NUMERIC, "C")
    except locale.Error as exc:            # never stop the app over this
        log.warning("could not pin LC_NUMERIC to C: %s", exc)
        return False
    log.debug("LC_NUMERIC pinned to C (was %s): macOS 27 native message "
              "boxes abort under a non-C number locale", before)
    return True
