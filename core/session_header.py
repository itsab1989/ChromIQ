# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The app log's session header (4.3.50, A1).

Written once by ``main()`` after the settings are loaded and the restart-to-apply
Betas are latched, so a tester's log says on its first screen which ChromIQ,
which system, which language and which Beta options produced what follows.
Every line starts ``session:`` and is ``key=value`` pairs, so it can be grepped.

The two answers that need a program to be started (ArgyllCMS's version, the
chart-reading helper's build) are asked on a background thread and logged as
one more ``session: tools`` line when they arrive: the start-up of the window is
not held for them. Nothing here raises into ``main()``.
"""
from __future__ import annotations

import locale
import platform
import sys
import threading

from core.beta_registry import (BETA_SUB_OPTIONS, BETA_SWITCHES, MEASURE_OPTIONS,
                                show)
from core.logger import get_logger

log = get_logger("chromiq.session")


def _os_text() -> str:
    try:
        from core.issue_report import detect_os_version
        return detect_os_version()
    except Exception:      # noqa: BLE001
        return platform.platform()


def _qt_versions() -> "tuple[str, str]":
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR, qVersion
        return str(qVersion()), str(PYQT_VERSION_STR)
    except Exception:      # noqa: BLE001
        return "-", "-"


def _numeric_locale() -> str:
    try:
        name = locale.setlocale(locale.LC_NUMERIC)        # a query: changes nothing
        point = locale.localeconv().get("decimal_point", "?")
        return f"{name}(decimal_point='{point}')"
    except Exception:      # noqa: BLE001
        return "-"


def _pairs(settings, keys) -> str:
    out = []
    for k in keys:
        try:
            out.append(f"{k}={show(settings.get(k))}")
        except Exception:      # noqa: BLE001
            out.append(f"{k}=?")
    return " ".join(out)


def _latched() -> str:
    """The restart-to-apply Betas as THIS session runs them (Preferences may
    already say otherwise until the next start)."""
    out = []
    for name, mod, fn in (("fd9", "workflow.fd9.support", "fd9_enabled"),
                          ("i1io", "workflow.i1io.support", "i1io_enabled"),
                          ("isis", "workflow.isis.support", "isis_enabled"),
                          ("page_output", "workflow.page_output.support",
                           "page_output_enabled")):
        try:
            import importlib
            out.append(f"{name}={show(bool(getattr(importlib.import_module(mod), fn)()))}")
        except Exception:      # noqa: BLE001
            out.append(f"{name}=?")
    return " ".join(out)


def header_lines(settings) -> "list[str]":
    """The header as text (no I/O beyond the platform's own cheap answers)."""
    try:
        from core.version import APP_VERSION
    except Exception:      # noqa: BLE001
        APP_VERSION = "unknown"
    qt, pyqt = _qt_versions()
    lang = "-"
    try:
        lang = show(settings.get("language", "en"))
    except Exception:      # noqa: BLE001
        pass
    return [
        f"session: chromiq={APP_VERSION} frozen={show(bool(getattr(sys, 'frozen', False)))} "
        f"os={show(_os_text())} arch={show(platform.machine())} "
        f"python={sys.version.split()[0]} qt={qt} pyqt={pyqt}",
        f"session: language={lang} numeric_locale={_numeric_locale()}",
        "session: beta " + _pairs(settings, BETA_SWITCHES),
        "session: beta_options " + _pairs(settings, BETA_SUB_OPTIONS),
        "session: beta_in_effect " + _latched() + " (restart-to-apply, as this session runs)",
        "session: options " + _pairs(settings, MEASURE_OPTIONS),
    ]


def tools_line(argyll_dir: str) -> str:
    """ArgyllCMS's version and folder, and the helper's build (starts programs;
    reads no settings, so it may run on a thread)."""
    source = "settings"
    version = "-"
    try:
        from pathlib import Path
        from core.issue_report import detect_argyll_version
        if not argyll_dir or not Path(argyll_dir).is_dir():
            from core.argyll_detect import find_argyll_bin_path
            found = find_argyll_bin_path()
            argyll_dir, source = (str(found), "auto-detected") if found else ("", "not found")
        text = detect_argyll_version(argyll_dir) if argyll_dir else ""
        version = text.split(",")[0] if text and not text.startswith("installed") else "-"
    except Exception:      # noqa: BLE001
        pass
    build, helper, caps = "-", "-", ""
    try:
        from workflow.chartread_engine import helper_build, helper_path
        hp = helper_path()
        helper = str(hp)
        from workflow.ti3_provenance import short_build
        full = helper_build(hp) or ""
        build = short_build(full) or "-"
        caps = full.split("+", 1)[1] if "+" in full else ""
    except Exception:      # noqa: BLE001
        helper = "not present"
    return (f"session: tools argyll={version} argyll_dir={argyll_dir or '-'} "
            f"argyll_found_by={show(source)} helper_build={show(build)} helper={helper}"
            + (f" helper_caps={caps}" if caps else ""))


def write_session_header(settings, *, tools_in_background: bool = True) -> None:
    """Log the header; never raises."""
    try:
        for line in header_lines(settings):
            log.info("%s", line)
    except Exception:      # noqa: BLE001
        log.debug("session header failed", exc_info=True)

    try:
        argyll_dir = str(settings.get("argyll_bin_path", "") or "")
    except Exception:      # noqa: BLE001
        argyll_dir = ""

    def _tools():
        try:
            log.info("%s", tools_line(argyll_dir))
        except Exception:      # noqa: BLE001
            log.debug("session tools line failed", exc_info=True)
    try:
        if tools_in_background:
            threading.Thread(target=_tools, name="chromiq-session-tools",
                             daemon=True).start()
        else:
            _tools()
    except Exception:      # noqa: BLE001
        pass
