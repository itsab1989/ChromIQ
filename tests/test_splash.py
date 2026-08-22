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
    app = QApplication.instance() or QApplication([])
    for f in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))
    return app


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
    """QSplashScreen hides on a click and the replacement must too: the Argyll
    not-found dialog is opened with exec() from MainWindow.__init__, i.e. while
    the splash is still up and always-on-top."""
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
