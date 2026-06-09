"""ChromIQ — Printer Profiling GUI.  Entry point."""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# Configure logging FIRST, before any heavy third-party imports (PyQt6, numpy,
# etc.).  If a frozen bundle ships with a broken dylib graph, the import below
# will crash before any application code runs — and without an early file
# handler that crash leaves no on-disk trace (see issue #11/#13).  core.logger
# and core.platform_paths use stdlib only, so they are safe to import here.
from core.logger import configure_logging, get_logger

configure_logging()
log = get_logger("chromiq")


def _log_excepthook(exc_type, exc, tb):
    log.critical(
        "Uncaught exception:\n%s",
        "".join(traceback.format_exception(exc_type, exc, tb)),
    )
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _log_excepthook

# Native crash capture. A fatal signal (SIGSEGV/SIGABRT) raised inside Qt or
# Chromium teardown — e.g. SIP following a freed C++ pointer during the window's
# closeEvent — never reaches _log_excepthook above; it kills the process with no
# Python traceback, and on macOS may not even leave a Console crash report the
# user can locate. faulthandler dumps the active Python stack of every thread on
# any fatal signal, so the next such crash lands in ChromIQ's own log directory
# (next to chromiq.log) where the user already looks. The file handle is kept at
# module scope for the whole process lifetime because faulthandler writes to the
# raw fd directly — letting it be garbage-collected would close the fd.
import faulthandler  # noqa: E402

_crash_log = None
try:
    from datetime import datetime as _dt

    from core.platform_paths import log_dir as _log_dir

    _crash_dir = _log_dir()
    _crash_dir.mkdir(parents=True, exist_ok=True)
    _crash_log = open(_crash_dir / "chromiq-crash.log", "a", encoding="utf-8")
    _crash_log.write(f"\n=== faulthandler armed {_dt.now():%Y-%m-%d %H:%M:%S} ===\n")
    _crash_log.flush()
    faulthandler.enable(file=_crash_log, all_threads=True)
except Exception:
    log.debug("Could not arm faulthandler to crash log; using stderr", exc_info=True)
    faulthandler.enable()

log.info(
    "ChromIQ starting; python=%s platform=%s frozen=%s argv=%s",
    sys.version.split()[0],
    sys.platform,
    getattr(sys, "frozen", False),
    sys.argv,
)

# Windows ARM: GPU is blocklisted for WebGL but the software compositor works fine.
# --ignore-gpu-blocklist re-enables WebGL; --disable-gpu-compositing keeps the
# compositor on the software path so the blocklist bypass doesn't break rendering.
if sys.platform == "win32":
    # Give Windows an explicit AppUserModelID before any window appears, so the
    # taskbar treats ChromIQ as its own app and shows the window icon set below
    # via setWindowIcon(). Without it the taskbar button inherits the host
    # process's icon (python.exe when run from source, the PyInstaller
    # bootloader when frozen), so the app icon never shows. Must run before the
    # first window is created — doing it at import is the earliest safe point.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ChromIQ.PrinterProfiling"
        )
    except Exception:
        log.debug("Could not set Windows AppUserModelID", exc_info=True)

    _existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    _extra = "--ignore-gpu-blocklist --disable-gpu-compositing"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{_existing} {_extra}".strip()

try:
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    # QtWebEngine must be imported before QApplication is instantiated.
    # Wrapped in try/except so the app still starts if the package is absent.
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        log.warning("QtWebEngine not available — gamut viewer will be disabled")

    from PyQt6.QtGui import QFontDatabase
    from core.resource_path import resource_path
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter
except BaseException:
    log.exception("Fatal error importing application modules")
    raise


def main() -> int:
    from core.version import APP_VERSION

    app = QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("ChromIQ")
    app.setApplicationDisplayName("ChromIQ — Printer Profiling")

    try:
        for font_path in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(font_path))
    except Exception:
        pass  # fonts dir missing — app falls back to system fonts

    app.setStyle(WinButtonLayoutStyle("Fusion"))

    _btn_font_filter = ButtonFontFilter(app)
    app.installEventFilter(_btn_font_filter)

    _gb_surface_filter = GroupBoxSurfaceFilter(app)
    app.installEventFilter(_gb_surface_filter)

    settings = AppSettings()
    appearance = settings.get("appearance", "auto")
    apply_appearance(app, None, appearance)

    icon_path = resource_path("assets/app_icon.png")
    log.debug("App icon: %s  exists=%s", icon_path, icon_path.exists())
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    win = MainWindow(settings)
    apply_appearance(app, win, settings.get("appearance", "auto"))

    def _on_system_color_scheme_changed(_scheme=None) -> None:
        # Only re-apply when user is following the system; explicit picks stay put.
        if settings.get("appearance", "auto") == "auto":
            apply_appearance(app, win, "auto")

    app.styleHints().colorSchemeChanged.connect(_on_system_color_scheme_changed)

    win.show()

    # Belt-and-braces re-apply for the maximize / fullscreen state. The bytes
    # from saveGeometry() carry it on most platforms, but explicit re-apply
    # avoids edge cases where the OS misses the transition. Scheduled via
    # QTimer.singleShot(0, ...) rather than called inline so the show() above
    # has actually been processed by the OS before we request a state change
    # — calling showFullScreen() in the same tick as show() can be dropped
    # on macOS.
    from PyQt6.QtCore import QTimer
    if settings.get("window_fullscreen", False):
        QTimer.singleShot(0, win.showFullScreen)
    elif settings.get("window_maximized", False):
        QTimer.singleShot(0, win.showMaximized)

    if settings.get("show_welcome_dialog", True):
        # Welcome dialog is non-modal (see MainWindow.open_welcome_dialog),
        # so it no longer blocks the event loop or preempts the maximize /
        # fullscreen animation. A small delay still lets the main window
        # finish its initial paint before the dialog steals focus.
        QTimer.singleShot(100, win.open_welcome_dialog)

    log.info("Event loop starting")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
