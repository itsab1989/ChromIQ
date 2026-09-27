"""B8-1405: a greyed folder button in Create Chart keeps the Create Chart hue.

The beta 44 release check photographed Guided's "Refinement profile" browse as
the plain folder beside the magenta Presets row. The button did ask for
"folder_create"; it was GREYED (it stays greyed until "Refinement profile" is
ticked), and Qt draws a disabled icon as a grey copy of it. A tab's folder
button now keeps its hue when greyed in Light and Dark, faded; Neutral keeps
Qt's grey, its one disabled look (and its enabled folders are ACTION anyway).

Mutations (each run red): M1405-a no Disabled pixmap in `load_folder_icon`;
M1405-b the plain "folder" given one too; M1405-c the faded copy drawn at full
strength; M1405-d the Disabled pixmap added under Neutral as well.
"""
from __future__ import annotations

import colorsys
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtGui import QIcon                                   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _ink(icon: QIcon, mode) -> "tuple[float, float, float] | None":
    """(hue 0..360, saturation, mean alpha) of the glyph's visible pixels."""
    img = icon.pixmap(20, 20, mode).toImage()
    r = g = b = n = 0
    alpha = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() >= 40:
                # un-premultiplied colour
                r += c.red(); g += c.green(); b += c.blue(); n += 1
                alpha += c.alpha()
    if not n:
        return None
    h, _l, s = colorsys.rgb_to_hls(r / n / 255, g / n / 255, b / n / 255)
    return h * 360, s, alpha / n


@pytest.fixture
def mode(monkeypatch):
    from ui import theme

    def use(m):
        monkeypatch.setattr(theme, "active_mode", lambda *a, **k: m)
    return use


@pytest.mark.parametrize("appearance", ["light", "dark"])
def test_a_greyed_create_chart_folder_is_still_magenta(qapp, mode, appearance):
    from ui.widgets import load_folder_icon
    mode(appearance)
    icon = load_folder_icon("folder_create")
    on = _ink(icon, QIcon.Mode.Normal)
    off = _ink(icon, QIcon.Mode.Disabled)
    assert on and off
    assert off[1] > 0.4, f"the greyed folder lost its colour: {off}"
    assert abs(off[0] - on[0]) < 12, (on, off)
    assert off[2] < on[2] * 0.7, "a greyed folder must look greyed (faded)"


@pytest.mark.parametrize("name", ["folder_print", "folder_measure",
                                  "folder_build", "folder_check"])
def test_every_tab_folder_keeps_its_hue_greyed(qapp, mode, name):
    from ui.widgets import load_folder_icon
    mode("light")
    icon = load_folder_icon(name)
    on = _ink(icon, QIcon.Mode.Normal)
    off = _ink(icon, QIcon.Mode.Disabled)
    assert abs(off[0] - on[0]) < 12 and off[1] > 0.3, (name, on, off)


def test_the_plain_folder_and_neutral_keep_qts_grey(qapp, mode):
    from ui.widgets import load_folder_icon
    mode("dark")
    assert load_folder_icon("folder").availableSizes(QIcon.Mode.Disabled) == []
    mode("neutral")
    assert load_folder_icon("folder_create").availableSizes(QIcon.Mode.Disabled) == []


def test_guideds_refinement_browse_is_the_create_chart_folder(qapp, mode, tmp_path):
    """The button itself: tagged folder_create (so a theme change reloads the
    same glyph), greyed until the box is ticked, and magenta while greyed."""
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    mode("light")
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    try:
        btn = tab._guided_precond_browse
        assert btn.property("themed_folder_icon") == "folder_create"
        assert not btn.isEnabled()
        off = _ink(btn.icon(), QIcon.Mode.Disabled)
        assert off[1] > 0.4, off
    finally:
        tab.deleteLater()
