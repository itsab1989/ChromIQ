"""Startup splash: renders a valid pixmap for both themes (no crash, sane size)."""
import os

import pytest

pytest.importorskip("PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QFontDatabase          # noqa: E402
from PyQt6.QtWidgets import QApplication, QSplashScreen  # noqa: E402

from core.resource_path import resource_path   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    """A QApplication with the bundled fonts, REMOVED AGAIN on teardown.

    The removal is not tidiness. ``QFontDatabase`` is global to the process, and
    an xdist worker runs many files in one process, so fonts added here stay
    visible to every file that follows on the same worker. That silently
    switches off ``tests/_fontcheck.py``'s guard for those files: on Windows the
    offscreen font database is empty and they are meant to skip, but with these
    six bundled faces registered they RUN — and then measure real assertions
    against three fonts instead of the system's, and fail. Which files are
    affected depends on how ``--dist loadfile`` packs them onto workers, so the
    failures move around between runs and look like flakiness.
    """
    app = QApplication.instance() or QApplication([])
    ids = []
    for f in resource_path("assets/fonts").glob("*.ttf"):
        fid = QFontDatabase.addApplicationFont(str(f))
        if fid != -1:
            ids.append(fid)
    yield app
    for fid in ids:
        QFontDatabase.removeApplicationFont(fid)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_splash_pixmap_renders(qapp, mode):
    from ui.splash import make_splash_pixmap
    pm = make_splash_pixmap(mode, "v9.9.9")
    assert not pm.isNull()
    assert pm.width() >= 600 and pm.height() >= 300   # logical 640x400, DPR-scaled


def test_make_splash_returns_ready_splashscreen(qapp):
    """The default is now a plain frameless window, not Qt's QSplashScreen —
    whose show() burns ~1 s on a bounded wait for a condition that never becomes
    true (measured 1043 ms against 13.6 ms). The classic one stays available."""
    from ui.splash import PlainSplash, make_splash
    splash = make_splash("dark", "v9.9.9")
    assert isinstance(splash, PlainSplash)
    assert not splash._pm.isNull()
    # LOGICAL size, not the pixmap's device size. On a Retina screen the pixmap
    # is 1280x800 at ratio 2 for a 640x400 window, and this line asserted the
    # bug Basti caught on the first real launch: sized from pixmap.size(), the
    # window came up twice as large with the artwork in its top-left quarter.
    # Green only at ratio 1, which is what the test suite runs at.
    assert splash.size() == splash._pm.deviceIndependentSize().toSize()
    # The escape hatch behind the "Classic splash screen" setting.
    classic = make_splash("dark", "v9.9.9", plain=False)
    assert isinstance(classic, QSplashScreen)
    assert not classic.pixmap().isNull()


def test_the_plain_splash_waits_for_the_screen_not_for_a_timeout(qapp):
    """The splash exists so the user can see the app has started, so it must be
    PAINTED before the build blocks the thread — the first implementation showed
    nothing and then flashed just before the main window.

    It waits on isExposed(), which means "on screen", rather than isVisible(),
    which is true 1.8 ms in while nothing is drawn. And the wait is BOUNDED: a
    session that never exposes the window must cost a fraction of a second, not
    the launch.
    """
    import inspect
    import time
    from ui.splash import PlainSplash, make_splash
    src = inspect.getsource(PlainSplash.wait_until_visible)
    assert "isExposed" in src and "isVisible" not in src
    assert "timeout_s" in inspect.signature(
        PlainSplash.wait_until_visible).parameters

    s = make_splash("dark", "v9.9.9")
    t0 = time.perf_counter()
    s.wait_until_visible(timeout_s=0.15)          # offscreen: never exposed
    assert time.perf_counter() - t0 < 1.0, (
        "the wait is not bounded — a session that cannot expose the splash "
        "would stall the launch")
    s.finish(None)


def test_the_splash_can_be_clicked_away(qapp):
    """QSplashScreen hides on a click and the replacement must too.

    NOTE what this does NOT prove. It calls ``mousePressEvent`` directly, so it
    asserts that the method body hides the widget — never that a click reaches
    it. Qt discards mouse events to windows a modal has blocked, so this test
    stayed green for the whole life of the bug it was written to guard against
    (a modal trapped under the splash). That is what
    ``test_the_splash_steps_aside_for_a_modal_dialog`` below is for; keep both,
    and do not let this one's green stand in for the other's.
    """
    from ui.splash import make_splash
    s = make_splash("dark", "v9.9.9")
    s.show()
    assert hasattr(s, "mousePressEvent")
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5.0, 5.0),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier)
    s.mousePressEvent(ev)
    assert not s.isVisible(), "the splash cannot be dismissed"
    s.finish(None)


@pytest.mark.parametrize("plain", [True, False], ids=["plain", "classic"])
def test_the_splash_steps_aside_for_a_modal_dialog(qapp, plain):
    """A modal opened while the splash is up must not be covered by it.

    THE BUG THIS PINS. The splash is always-on-top; a modal dialog is not, and
    on Windows a non-topmost window can never be raised above a topmost one. So
    the first-launch "ArgyllCMS not found" dialog came up UNDER the splash,
    ~83% covered, with its buttons swallowed by the disabled splash on top —
    reachable only by Alt+Tab. Clicking the splash away could not rescue it,
    because Qt discards mouse events to blocked windows.

    Driven through a REAL ``exec()`` rather than by calling a handler, which is
    the only way this could have been caught. Both splashes are covered: Qt's
    own QSplashScreen ignores WindowBlocked, so the "Classic splash screen"
    setting reproduced the bug verbatim until ClassicSplash existed.
    """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QDialog, QMainWindow
    from ui.splash import make_splash

    owner = QMainWindow()
    s = make_splash("dark", "v9.9.9", plain=plain)
    s.show()
    qapp.processEvents()
    assert s.isVisible()

    dlg = QDialog(owner)
    seen = {}

    def _look_then_close():
        seen["visible_during_modal"] = s.isVisible()
        dlg.accept()

    QTimer.singleShot(50, _look_then_close)
    dlg.exec()
    qapp.processEvents()

    assert seen["visible_during_modal"] is False, (
        "the splash stayed on screen over a modal dialog — on Windows that "
        "dialog is unreachable, because a non-topmost modal cannot rise above "
        "an always-on-top splash and the splash swallows clicks aimed at it")
    assert s.isVisible(), (
        "the splash did not come back once the modal closed — startup is still "
        "in progress and the branding must not vanish early")
    s.finish(None)
    owner.close()


def test_the_splash_stays_gone_after_finish(qapp):
    """Once finished, no later modal may summon the splash back.

    ``finish()`` only closes the widget; the object lives as long as ``main()``,
    which does not return until the app quits. So the WindowBlocked handler runs
    for every modal in the whole session, and without the ``_finished`` guard
    the splash would reappear over, say, Preferences three hours in.
    """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QDialog, QMainWindow
    from ui.splash import make_splash

    owner = QMainWindow()
    s = make_splash("dark", "v9.9.9")
    s.show()
    qapp.processEvents()
    s.finish(None)
    qapp.processEvents()
    assert not s.isVisible()

    dlg = QDialog(owner)
    QTimer.singleShot(50, dlg.accept)
    dlg.exec()
    qapp.processEvents()

    assert not s.isVisible(), (
        "a finished splash came back for a later modal — it would sit on top "
        "of a dialog long after startup")
    owner.close()


def test_no_modal_escapes_the_main_window_constructor(qapp, tmp_path, monkeypatch):
    """The ArgyllCMS dialog must not be raised from ``MainWindow.__init__``.

    That is where it used to live, which is the whole reason it could be trapped
    under the splash: ``__init__`` runs at main.py's ``MainWindow(settings)``,
    long before ``win.show()`` and ``splash.finish(win)``. Deferring it is what
    makes the window and the splash state well-defined by the time it appears.

    The status line, the auto-detect and the settings write deliberately stay in
    the constructor — only the modal moved — so this asserts the split, not just
    the absence.
    """
    import ui.main_window as mw
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    calls = []
    monkeypatch.setattr(MainWindow, "_show_argyll_not_found_dialog",
                        lambda self: calls.append("shown"))
    # Pretend this machine has no ArgyllCMS: the configured path is empty AND
    # auto-detection finds nothing, which is the real first-launch case.
    monkeypatch.setattr(mw, "find_argyll_bin_path", lambda: None)

    settings = AppSettings()
    monkeypatch.setattr(settings, "get",
                        lambda k, d=None, _o=settings.get: (
                            str(tmp_path / "no-argyll-here")
                            if k == "argyll_bin_path" else _o(k, d)))

    win = MainWindow(settings)
    try:
        assert calls == [], (
            "MainWindow.__init__ opened a modal dialog — it runs while the "
            "always-on-top splash is up, so the dialog is unreachable")
        assert win._argyll_missing_at_start is True, (
            "the missing-ArgyllCMS state was not recorded for later")
        assert win._status_msg, "the status-bar warning must still be set in __init__"

        win.show_startup_warnings()
        assert calls == ["shown"], "the deferred dialog never appeared"
        win.show_startup_warnings()
        assert calls == ["shown"], "the deferred dialog fired twice"
    finally:
        win.close()


def test_main_actually_calls_show_startup_warnings():
    """``main()`` must WIRE the deferred dialog, not merely make it possible.

    Without this, deleting one line from main.py leaves every other test in this
    file green while a first-launch user with no ArgyllCMS gets a status-bar
    line and no dialog at all — a quieter version of the bug being fixed, and
    exactly what a future "tidy up main()" commit produces.

    Both start-up windows now come out of one function, ``_open_startup_windows``
    — which is what makes them a SEQUENCE (welcome first, modal 150 ms behind it)
    on whichever release the fullscreen gate does or does not take.  The order
    inside it, and the gate itself, are pinned in
    ``test_first_launch_dialog_order.py``.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "main.py").read_text(
        encoding="utf-8")
    call = "QTimer.singleShot(150, win.show_startup_warnings)"
    welcome = "win.open_welcome_dialog()"
    assert call in src, (
        "main.py no longer calls show_startup_warnings — the first-launch "
        "ArgyllCMS dialog would never be shown at all")
    assert welcome in src, "the welcome-dialog wiring moved; re-check the order below"
    assert src.index(welcome) < src.index(call), (
        "the welcome dialog must be opened BEFORE the ArgyllCMS modal is "
        "queued, or its timer fires inside the modal's event loop and takes "
        "the keyboard from it")
