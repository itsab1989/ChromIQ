"""A scroll fade starts in the appearance on screen, and follows a switch.

Basti, 2026-11-11, watching Measurement info on screen in light mode: *"it is
a black gradient even though the app is in light mode"*. `FadeScrollArea`
and `EdgeFades` started as "dark" and waited for MainWindow's appearance
broadcast, which only reaches widgets that exist when it runs. Every window
built later from the Tools menu (Measurement info, Profile info, ...) kept a
black band at its scroll edges in light mode, in the real app (photographed
from `main.main()`), and so did 4.3.30.

Pinned here, without touching the suite's QApplication palette or style
sheet (`ui.theme.active_mode` is what the fades ask, and is stood in for):
* a fade built in light / dark / neutral takes that appearance's colour;
* both late-built info windows end up in it;
* an app-wide palette change while a fade is open moves it along.
"""
from __future__ import annotations

import os

import pytest
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication, QListWidget, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui import fade_scroll as F  # noqa: E402

MODES = ("light", "dark", "neutral")


def _on_screen(monkeypatch, mode):
    import ui.theme as T
    monkeypatch.setattr(T, "active_mode", lambda palette=None: mode)


def _colour(surface, mode):
    return F._SURFACES[surface][mode].lower()


@pytest.mark.parametrize("mode", MODES)
def test_a_fade_starts_in_the_appearance_on_screen(qapp, monkeypatch, mode):
    _on_screen(monkeypatch, mode)
    host = QWidget()
    for surface in ("panel", "dialog", "surface"):
        fs = F.FadeScrollArea(host, surface=surface)
        assert fs._top_fade._color.name() == _colour(surface, mode)
        assert fs._bot_fade._color.name() == _colour(surface, mode)
    ef = F.attach_edge_fades(QListWidget(host), surface="dialog")
    assert ef._top._color.name() == _colour("dialog", mode)
    host.deleteLater()


@pytest.mark.parametrize("mode", MODES)
def test_the_late_built_info_windows_take_it(qapp, monkeypatch, mode):
    from tests.test_profile_tools import _runner, _Settings
    from ui.dialogs.profile_info_dialog import ProfileInfoDialog
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    _on_screen(monkeypatch, mode)
    s = _Settings()
    s.set("appearance", mode)
    for cls in (Ti3InfoDialog, ProfileInfoDialog):
        dlg = cls(_runner(), s)
        want = _colour(dlg._scroll._surface, mode)
        assert dlg._scroll._top_fade._color.name() == want, cls.__name__
        dlg.deleteLater()


def test_an_appearance_switch_while_open_moves_the_fade(qapp, monkeypatch):
    _on_screen(monkeypatch, "dark")
    host = QWidget()
    fs = F.FadeScrollArea(host, surface="dialog")
    lw = QListWidget(host)
    ef = F.attach_edge_fades(lw, surface="dialog")
    assert fs._top_fade._color.name() == _colour("dialog", "dark")
    _on_screen(monkeypatch, "light")
    QApplication.sendEvent(fs, QEvent(QEvent.Type.ApplicationPaletteChange))
    QApplication.sendEvent(lw.viewport(),
                           QEvent(QEvent.Type.ApplicationPaletteChange))
    assert fs._top_fade._color.name() == _colour("dialog", "light")
    assert ef._top._color.name() == _colour("dialog", "light")
    host.deleteLater()
