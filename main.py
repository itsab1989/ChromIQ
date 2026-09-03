"""ChromIQ — Printer Profiling GUI.  Entry point."""
from __future__ import annotations

import logging
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

# The VERSION belongs in the very first line of every log. Without it a report
# cannot be matched to a build, and "is this fixed?" turns into guesswork about
# which release the user was actually running (#131, Knut 2026-07-27).
try:
    from core.version import APP_VERSION as _APP_VERSION
except Exception:      # noqa: BLE001 — never let logging block startup
    _APP_VERSION = "unknown"

log.info(
    "ChromIQ %s starting; python=%s platform=%s frozen=%s argv=%s",
    _APP_VERSION,
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
    # NB: ui.main_window (the whole UI tree, a heavy import) is imported inside
    # main() AFTER the splash is on screen, so the splash covers that cost too.
    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import (ButtonFontFilter, CompositeAppFilter, DialogFocusFilter,
                            GroupBoxSurfaceFilter, TooltipWrapFilter)
except BaseException:
    log.exception("Fatal error importing application modules")
    raise


def main() -> int:
    from core.version import APP_VERSION

    # Windows/ARM has no freetype-py wheel with a native lib; point it at our
    # vendored ARM64 FreeType so the vector-PDF export works (#72). No-op else.
    from core.freetype_bootstrap import ensure_freetype_library
    ensure_freetype_library()

    app = QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("ChromIQ")
    # The display name is set LATER, once the catalogue is loaded — see the
    # `setApplicationDisplayName` call below `set_language`.

    # Silence the cosmetic QtWebEngine/Chromium teardown warnings printed on the
    # crash-safe os._exit path (see core.qt_message_filter / core.webengine_shutdown).
    from core.qt_message_filter import install_qt_message_filter
    install_qt_message_filter(app)

    try:
        for font_path in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(font_path))
    except Exception:
        pass  # fonts dir missing — app falls back to system fonts

    app.setStyle(WinButtonLayoutStyle("Fusion"))

    # FOUR APP-WIDE FILTERS, ONE INSTALLED OBJECT.
    #
    # Qt dispatches an application filter to every installed filter for every
    # event; with four of them that is ~993,000 crossings into Python per launch,
    # ~1074 ms of which is the crossing rather than the work. CompositeAppFilter
    # runs the same four, in the same order Qt would have used (reverse install
    # order), and returns early on the three event types any of them acts on.
    #
    # The four are: button-font fitting, group-box surfaces, tooltip word-wrap
    # (#70 — long tooltips must not run off-screen; it exists because of
    # Windows), and the space bar not activating a dialog's auto-focused button
    # (Knut). CHROMIQ_SEPARATE_FILTERS=1 installs them separately again, for a
    # build that is already out and cannot be patched.
    if os.environ.get("CHROMIQ_SEPARATE_FILTERS") == "1":
        _btn_font_filter = ButtonFontFilter(app)
        app.installEventFilter(_btn_font_filter)
        _gb_surface_filter = GroupBoxSurfaceFilter(app)
        app.installEventFilter(_gb_surface_filter)
        _tooltip_wrap_filter = TooltipWrapFilter(app)
        app.installEventFilter(_tooltip_wrap_filter)
        _dialog_focus_filter = DialogFocusFilter(app)
        app.installEventFilter(_dialog_focus_filter)
        log.info("Event filters installed separately (CHROMIQ_SEPARATE_FILTERS=1)")
    else:
        _app_filter = CompositeAppFilter(app)
        app.installEventFilter(_app_filter)

    settings = AppSettings()
    settings.migrate()   # drop persisted values that only echo a superseded default
    from core.platform_paths import set_icc_install_override
    set_icc_install_override(str(settings.get("profile_install_dir", "")))

    # Language must be set before any widget is built — strings are
    # translated at construction time (restart-to-apply, see core/i18n.py).
    from core.i18n import install_qt_translator, set_language, tr
    set_language(settings.get("language", "en"))
    # AFTER `set_language`, AND THROUGH `tr` — both halves, or the title bar
    # says it twice in two languages. Qt appends the application display name
    # to every window title unless the title already ends with it
    # (`QPlatformWindow::formatWindowTitle`), and the main window's own title is
    # this same sentence. Set in English while the app runs in German, the two
    # stopped matching and Windows showed
    # "ChromIQ — Druckerprofilierung - ChromIQ — Printer Profiling" on every
    # window and in the task bar (Windows 11 VM, German UI, 2026-09-03).
    # Set here, they match again and Qt appends nothing. It cannot move any
    # earlier: `tr` before `set_language` is the English catalogue.
    app.setApplicationDisplayName(tr("ChromIQ — Printer Profiling"))
    # Qt's own strings (OK/Cancel/Close buttons, context menus) come from
    # qtbase_<code>.qm, not our catalog.
    install_qt_translator(app)

    appearance = settings.get("appearance", "auto")
    mode = apply_appearance(app, None, appearance)

    icon_path = resource_path("assets/app_icon.png")
    log.debug("App icon: %s  exists=%s", icon_path, icon_path.exists())
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Startup splash: shown while the main window builds, theme-aware, dismissed
    # once the window is up.
    import time as _time
    from ui.splash import make_splash
    _SPLASH_MIN_S = 0.9          # keep it on screen at least this long (branding)

    def _pump(seconds: float) -> None:
        """Run the event loop for *seconds* so macOS actually composites the
        splash to the screen — a plain processEvents() paints it but the window
        server may not flush it before the blocking window build runs, which is
        why the splash used to only flash at the very end."""
        end = _time.monotonic() + seconds
        while _time.monotonic() < end:
            app.processEvents()
            _time.sleep(0.01)

    # The startup splash is optional (Settings → General). When off we skip
    # straight to the build with no branding screen and no minimum-time hold.
    show_splash = settings.get("show_splash", True)
    # "Classic splash screen" (Preferences -> Beta) restores Qt's QSplashScreen,
    # which costs ~1 s of the launch inside its own show(). Default is the plain
    # window: same pixmap, painted before the build, in 9-66 ms.
    _classic = bool(settings.get("splash_classic", False))
    splash = (make_splash(mode, f"v{APP_VERSION}", plain=not _classic)
              if show_splash else None)
    _splash_shown = _time.monotonic()
    if splash is not None:
        splash.show()
        splash.raise_()
        splash.repaint()
        # THE SPLASH MUST BE ON SCREEN BEFORE THE BUILD BLOCKS THE THREAD.
        # This is the whole reason it exists (users could not tell the app had
        # started), and the first implementation got it wrong — nothing, then a
        # flash just before the main window. Bounded, so a session that never
        # exposes it costs 0.3 s rather than the launch.
        if hasattr(splash, "wait_until_visible"):
            splash.wait_until_visible()
        _pump(0.18)             # get it on screen before the blocking build

    # Heavy UI import + construction, now visibly covered by the splash.
    from ui.main_window import MainWindow
    win = MainWindow(settings)
    apply_appearance(app, win, settings.get("appearance", "auto"))

    def _on_system_color_scheme_changed(_scheme=None) -> None:
        # Only re-apply when user is following the system; explicit picks stay put.
        if settings.get("appearance", "auto") == "auto":
            apply_appearance(app, win, "auto")

    app.styleHints().colorSchemeChanged.connect(_on_system_color_scheme_changed)

    # Hold the splash to its minimum on-screen time (only pads when the build was
    # faster than _SPLASH_MIN_S — usually it wasn't, so this adds nothing), then
    # reveal the window and dismiss the splash.
    if splash is not None:
        _pump(max(0.0, _SPLASH_MIN_S - (_time.monotonic() - _splash_shown)))
    win.show()
    if splash is not None:
        splash.finish(win)      # dismiss the splash now the window is up

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

    # Pay QtWebEngine's costly first-init now, at idle on the main loop and
    # outside any modal, so the chart-design windows' on-demand 3D-cube preview
    # never spins Chromium up mid-transition (issue #38 follow-up: that froze
    # the editor on Windows the first time the preview was opened).
    from core.webengine_warmup import warm_up_webengine
    QTimer.singleShot(0, warm_up_webengine)

    # Pre-warm the system-font map: the first chart render that uses a system
    # (non-bundled) font makes Pillow enumerate every installed font file, a
    # ~60 ms one-off hitch. It's pure Python (no Qt), so build the cache on a
    # daemon thread at idle; the result is an idempotent module-global, so a
    # concurrent on-demand build is harmless.
    def _warm_font_map() -> None:
        import threading

        def _run() -> None:
            try:
                from workflow.layout_engine.raster import _system_font_map
                _system_font_map()
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()
    QTimer.singleShot(1500, _warm_font_map)

    # ------------------------------------------------------------------
    # The two start-up windows: the welcome dialog, then the "ArgyllCMS not
    # found" modal 150 ms behind it.
    #
    # ORDER. The modal used to be opened from inside MainWindow.__init__ — i.e.
    # before win.show() and before splash.finish(), so it came up UNDER the
    # always-on-top splash and could not be clicked at all (Windows; only
    # Alt+Tab reached it). It waits until here: the window is up, the splash is
    # gone. It stays BEHIND the welcome dialog, because a modal opened while the
    # welcome dialog's own timer is still pending fires that timer inside the
    # modal's nested event loop: activateWindow() then runs on a window Qt has
    # already blocked, NSApp.keyWindow becomes "Welcome to ChromIQ" while the
    # modal is frontmost, and Return, Escape and Space do nothing.
    #
    # TIMING, on macOS with a fullscreen state to restore: NOT a fixed delay.
    # showFullScreen() there is NATIVE fullscreen — the window is moved to a
    # Space of its own, animated, and it is only over ~1.7 s in. A window shown
    # before that lands on whichever Space is active meanwhile, i.e. the old
    # one: measured, the welcome dialog stayed behind on the main Space while
    # the window went fullscreen on its own. And a MODAL shown before that makes
    # macOS abort the transition outright (NSWindowDidFailToEnterFullScreen):
    # the window drops to its plain geometry while isFullScreen() still returns
    # True, and MainWindow.closeEvent then files that lie, so the next launch
    # repeats it. Both faults predate this branch. See core/macos_fullscreen.py.
    def _open_startup_windows() -> None:
        if settings.get("show_welcome_dialog", True):
            # Non-modal (see MainWindow.open_welcome_dialog), so it never
            # blocks the event loop.
            win.open_welcome_dialog()
        QTimer.singleShot(150, win.show_startup_warnings)

    gated = False
    if settings.get("window_fullscreen", False):
        from core.macos_fullscreen import run_after_fullscreen_transition
        gated = run_after_fullscreen_transition(win, _open_startup_windows)
    if not gated:
        # No transition to wait for (every other platform, and any window state
        # but fullscreen). The small delay still lets the main window finish its
        # first paint before a dialog takes the focus.
        QTimer.singleShot(100, _open_startup_windows)

    log.info("Event loop starting")
    return app.exec()


def _hard_exit(code: int) -> None:
    """Flush our own buffers and hand straight to the OS, skipping CPython
    finalization.

    QtWebEngine + SIP crash on quit (issue #38). Once ``app.exec()`` returns
    the app is already shutting down and every bit of our own cleanup —
    settings save, ArgyllRunner shutdown, the per-view WebEngine drain — has
    already run inside ``MainWindow.closeEvent`` (while the event loop was
    still alive, which is the only safe time). What's left is pure teardown
    risk: letting the interpreter finalize from here runs SIP's ``atexit``
    ``cleanup_on_exit`` handler, which walks the Qt wrapper graph and follows a
    freed pointer into Chromium's already-released browser-main subtree —
    ``EXC_BAD_ACCESS`` in ``CrBrowserMain`` at ``_Py_Finalize``. This is *not*
    fixable by destroying individual web views: once any ``QWebEngineView`` has
    existed, WebEngine-global state (the default profile / Chromium main)
    outlives every view and is what the finalize walk trips over. So we don't
    finalize: flush logs and ``os._exit``, letting the OS reclaim everything.
    There are no ``atexit`` hooks of our own to lose."""
    try:
        logging.shutdown()
    except Exception:
        pass
    try:
        if _crash_log is not None:
            _crash_log.flush()
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    os._exit(code)


if __name__ == "__main__":
    _hard_exit(main())
