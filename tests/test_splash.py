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
    from ui.splash import make_splash
    splash = make_splash("dark", "v9.9.9")
    assert isinstance(splash, QSplashScreen)
    assert not splash.pixmap().isNull()
