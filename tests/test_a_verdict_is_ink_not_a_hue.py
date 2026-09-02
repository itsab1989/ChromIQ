"""Two verdicts that kept their hue in the colourless appearance.

Neither is visible at rest — both labels are `setVisible(False)` until
something happens — so every pixel census taken of the Neutral theme walked
straight past them:

* `MainWindow._set_tab_status(msg, warning=True)` painted `#3a2a00` with
  `#ffb42d` on it: a 60,000-pixel near-black brown slab with amber text, in a
  theme whose rule 2 is *"all text is dark, there is no inverted text
  anywhere"*. The commonest way to see it is a wrong ArgyllCMS binary path.
* `MarginInspectorPanel` painted "Margins: OK" in `#4fc27a` at **1.74:1** on
  the Neutral ground and a margin violation in `#e0564b` at **2.89:1**. The
  theme's own tertiary ink is 8.13:1 and its rule 3 says low contrast means
  "disabled" and nothing else — so a pass message the user is meant to read
  was fainter than the theme allows anything that works to be.

The pass and the failure do not need a hue to be told apart here: they differ
in their words, in weight, and in the leading warning sign, which is the
escalation `ui/neutral_styles.py` describes for this theme.

Light and Dark must keep the exact strings they always had, which is what
`ui.theme.ink_for` and `ui.theme.by_mode` guarantee — they return their Light
and Dark arguments unchanged.
"""
from __future__ import annotations

import re

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QWidget

from ui import neutral_styles as nm
from ui.light_styles import make_light_palette
from ui.neutral_styles import make_neutral_palette
from ui.styles import make_dark_palette

HEX = re.compile(r"#([0-9a-fA-F]{6})\b")

#: What Light and Dark painted before this fix, and must still paint.
SHIPPED = {
    "slab_bg":  "#3a2a00",
    "slab_ink": "#ffb42d",
    "ok":       "#4fc27a",
    "violation": "#e0564b",
    "quiet":    "#909090",
}

_PALETTES = {"light": make_light_palette, "dark": make_dark_palette,
             "neutral": make_neutral_palette}


def hues(text: str) -> list:
    """Every non-grey colour in a style string."""
    out = []
    for m in HEX.finditer(text):
        c = QColor("#" + m.group(1))
        if max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue()) > 8:
            out.append(c.name())
    return out


def _lin(v):
    v /= 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def contrast(a: str, b: str) -> float:
    ca, cb = QColor(a), QColor(b)
    la = 0.2126*_lin(ca.red()) + 0.7152*_lin(ca.green()) + 0.0722*_lin(ca.blue())
    lb = 0.2126*_lin(cb.red()) + 0.7152*_lin(cb.green()) + 0.0722*_lin(cb.blue())
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


@pytest.fixture
def wearing(qapp):
    """Put an appearance's PALETTE on the app and put the old one back.

    Never `apply_appearance`: an app-wide stylesheet re-polishes every widget
    the suite has alive. `ink_for` / `by_mode` read the palette, which is all
    these two call sites need.
    """
    original = qapp.palette()

    def _wear(mode: str):
        qapp.setPalette(_PALETTES[mode]())
        return mode

    yield _wear
    qapp.setPalette(original)


# ----------------------------------------------------------------------
# MainWindow._set_tab_status — driven for real, with stub collaborators.
# ----------------------------------------------------------------------
class _StubTab:
    def __init__(self, parent):
        self._status_bar_lbl = QLabel("", parent)


class _StubWindow:
    """Only what `_set_tab_status` touches. The METHOD under test is the real
    one — `MainWindow._set_tab_status` is called unbound, so nothing here
    re-implements it."""

    def __init__(self, parent):
        self._tab_chart = _StubTab(parent)
        self._tab_print = _StubTab(parent)
        self._tab_measure = _StubTab(parent)


def _drive_status(host, msg, warning):
    from ui.main_window import MainWindow
    w = _StubWindow(host)
    MainWindow._set_tab_status(w, msg, warning=warning)
    return w._tab_chart._status_bar_lbl.styleSheet()


def test_the_tab_status_warning_carries_no_hue_in_neutral(wearing, qapp):
    wearing("neutral")
    host = QWidget()
    qss = _drive_status(host, "ArgyllCMS binaries were not found.", True)
    assert hues(qss) == [], f"the warning slab still carries {hues(qss)}"
    assert nm.NM_BG_SURFACE in qss and nm.NM_TEXT_MAIN in qss, qss
    host.deleteLater()


@pytest.mark.parametrize("mode", ("light", "dark"))
def test_the_tab_status_warning_did_not_move(wearing, qapp, mode):
    wearing(mode)
    host = QWidget()
    qss = _drive_status(host, "ArgyllCMS binaries were not found.", True)
    assert SHIPPED["slab_bg"] in qss and SHIPPED["slab_ink"] in qss, qss
    host.deleteLater()


def test_the_quiet_tab_status_is_not_faint_enough_to_read_as_disabled(
        wearing, qapp):
    wearing("neutral")
    host = QWidget()
    qss = _drive_status(host, "A quiet note.", False)
    ink = HEX.search(qss).group(0)
    assert contrast(ink, nm.NM_BG_WINDOW) >= 8.0, (
        f"{ink} is {contrast(ink, nm.NM_BG_WINDOW):.2f}:1 on the ground; "
        "in this theme that reads as disabled")
    host.deleteLater()


# ----------------------------------------------------------------------
# MarginInspectorPanel — the real widget, the real method.
# ----------------------------------------------------------------------
def _panel(qapp):
    from ui.margin_inspector_panel import MarginInspectorPanel
    return MarginInspectorPanel()


def _violation():
    from ui.margin_inspector_panel import Violation
    return Violation(edge="left", measured_mm=4.0, threshold_mm=10.0)


@pytest.mark.parametrize("violations,name", (([], "Margins: OK"),
                                             ("one", "a violation")))
def test_the_margin_verdict_is_dark_ink_in_neutral(wearing, qapp, violations,
                                                   name):
    wearing("neutral")
    p = _panel(qapp)
    vs = [_violation()] if violations == "one" else []
    p._update_status(vs, thresholds_defined=True, notify=True)
    qss = p._status.styleSheet()
    assert hues(qss) == [], f"{name} still carries {hues(qss)}"
    ink = HEX.search(qss).group(0)
    assert contrast(ink, nm.NM_BG_WINDOW) >= 8.0, (
        f"{name} is {contrast(ink, nm.NM_BG_WINDOW):.2f}:1 on the ground")
    p.deleteLater()


@pytest.mark.parametrize("mode", ("light", "dark"))
@pytest.mark.parametrize("violations,expected",
                         (([], SHIPPED["ok"]),
                          ("one", SHIPPED["violation"])))
def test_the_margin_verdict_did_not_move(wearing, qapp, mode, violations,
                                         expected):
    wearing(mode)
    p = _panel(qapp)
    vs = [_violation()] if violations == "one" else []
    p._update_status(vs, thresholds_defined=True, notify=True)
    assert expected in p._status.styleSheet(), p._status.styleSheet()
    p.deleteLater()


def test_a_verdict_already_on_screen_follows_a_live_switch(wearing, qapp):
    """The style is per-widget, so nothing else would refresh it."""
    wearing("light")
    p = _panel(qapp)
    p._update_status([], thresholds_defined=True, notify=True)
    assert SHIPPED["ok"] in p._status.styleSheet()

    wearing("neutral")
    p.set_appearance("neutral")
    assert hues(p._status.styleSheet()) == [], (
        "the verdict kept its hue after a switch to Neutral")

    wearing("light")
    p.set_appearance("light")
    assert SHIPPED["ok"] in p._status.styleSheet(), (
        "the verdict did not get its green back")
    p.deleteLater()
